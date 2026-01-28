# ToP/services/hold_requests_service.py

import json
import traceback
import threading
import requests

from ..models import (
    Sales,
    SalesHead,
    SalesRequest,
    Unit,
    Project,
    ProjectWebConfiguration,
)

from ..utils.notifications_utils import (
    email_thread_target,
    notify_company_controllers,
    send_pusher_notification,
)


from ..services.erp_unit_mapping_service import ERPUnitMappingService
from ..services.erp_hold_post_mapping_service import ERPHoldPostMappingService
from ..utils.erp_mapping_utils import apply_header_mapping

class HoldRequestsManagementService:
    """
    Service layer for Hold Requests workflows.
    - DOES NOT take HttpRequest.
    - Unified Logic: Local DB is the Source of Truth.
    - ERP acts as a synchronized external system if enabled.
    """

    # =========================================================
    # PUBLIC: SEND HOLD (Triggered via AJAX / Modal)
    # =========================================================
    @staticmethod
    def send_hold_to_erp(*, user, payload: dict):
        """
        Processes a hold request.
        Name preserved as 'send_hold_to_erp' for view compatibility,
        but logic is now Unified (Local First + ERP Sync).
        """
        try:
            company_user = None
            company = None

            sales_head_profile = SalesHead.objects.filter(user=user).select_related("company").first()
            if sales_head_profile and sales_head_profile.company:
                company_user = sales_head_profile
                company = sales_head_profile.company
            else:
                sales_profile = Sales.objects.filter(user=user).select_related("company").first()
                if sales_profile and sales_profile.company:
                    company_user = sales_profile
                    company = sales_profile.company
            
            
            data = dict(payload)  # copy to mutate safely

            # Cleanup for storage
            client_name = data.get("client_name")
            client_phone_number = data.get("client_phone_number")
            
            if "client_name" in data: del data["client_name"]
            if "client_phone_number" in data: del data["client_phone_number"]

            project_name = data.get("project_name", "")
            project = Project.objects.filter(name=project_name, company=company).first()
            unit_code = data["unitCode"]

            # --- EXECUTE UNIFIED HOLD LOGIC ---
            result = HoldRequestsManagementService._execute_unified_hold(
                user=user,
                company=company,
                project=project,
                unit_code=unit_code,
                data=data,
                client_name=client_name,
                client_phone_number=client_phone_number
            )

            return result

        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "status": 500,
                "payload": {"status": "error", "message": f"Unexpected error: {str(e)}"},
            }

    # =========================================================
    # PUBLIC: SAVE UNIT TO SESSION (Triggered via Save & Add)
    # =========================================================
    @staticmethod
    def save_unit_to_session(*, user, post_data):
        """
        Processes a hold request AND adds it to the user's session list.
        """
        messages_out = []
        session_ops = []

        try:
            company_user = None
            company = None

            sales_head_profile = SalesHead.objects.filter(user=user).select_related("company").first()
            if sales_head_profile and sales_head_profile.company:
                company_user = sales_head_profile
                company = sales_head_profile.company
            else:
                sales_profile = Sales.objects.filter(user=user).select_related("company").first()
                if sales_profile and sales_profile.company:
                    company_user = sales_profile
                    company = sales_profile.company

            raw_data = post_data.get("payment_data")
            data_json = post_data.get("payment_all_data")

            if not data_json:
                return {
                    "success": False,
                    "messages": [{"level": "error", "text": "No payment_all_data received"}],
                    "redirect": "home",
                }

            data = json.loads(data_json)
            project = Project.objects.filter(name=data.get("project_name", "")).first()
            unit_code = data["unitCode"]

            # --- EXECUTE UNIFIED HOLD LOGIC ---
            # Extract client info from data payload if not passed explicitly
            client_name = data.get("client_name")
            client_phone = data.get("client_phone_number")

            result = HoldRequestsManagementService._execute_unified_hold(
                user=user,
                company=company,
                project=project,
                unit_code=unit_code,
                data=data,
                client_name=client_name,
                client_phone_number=client_phone
            )

            # Map Service Result to Session View Result
            if not result.get("success"):
                # Extract error message from payload
                msg = result.get("payload", {}).get("message", "Unknown Error")
                return {
                    "success": False,
                    "messages": [{"level": "error", "text": msg}],
                    "redirect": "home",
                }

            # --- SESSION STORAGE ---
            # If hold was successful, add to session storage for the "Saved Units" sidebar
            if not raw_data:
                # Should typically not happen if logic passed, but safe guard
                payment_data = data.get("payments", [])
            else:
                try:
                    payment_data = json.loads(raw_data)
                except json.JSONDecodeError:
                    payment_data = []

            unit_obj = {
                "unit_code": unit_code,
                "payments": payment_data,
            }

            session_ops.append({"op": "append", "key": "saved_units", "value": unit_obj})
            messages_out.append({"level": "success", "text": "Unit Held Successfully!"})

            return {
                "success": True,
                "messages": messages_out,
                "session_ops": session_ops,
                "redirect": "home",
            }

        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "messages": [{"level": "error", "text": f"Unexpected error: {str(e)}"}],
                "redirect": "home",
            }

    # =========================================================
    # CORE: UNIFIED HOLD LOGIC
    # =========================================================
    @staticmethod
    def _execute_unified_hold(*, user, company, project, unit_code, data, client_name=None, client_phone_number=None):
        """
        The Single Source of Truth for holding a unit.
        
        Flow:
        1. Find Unit in Local DB (Data Hub).
        2. Check Local Status (Must be 'Available').
        3. If ERP Enabled:
           a. Check ERP Status.
           b. POST Block to ERP.
        4. Update Local Unit (Status -> 'Hold').
        5. Create Sales Request.
        6. Send Notifications.
        """
        
        # 1. Find Unit in Local DB (Robust Lookup)
        # Try exact match first
        unit = Unit.objects.filter(unit_code=unit_code, company=company).first()
        
        # Try stripping suffix if exact match fails (e.g. "U101_MyComp")
        if not unit:
            clean_code = unit_code.split("_")[0]
            unit = Unit.objects.filter(unit_code=clean_code, company=company).first()

        if not unit:
            # Critical: Data Hub out of sync or bad request
            return {
                "success": False, 
                "status": 404, 
                "payload": {"status": "error", "message": "Unit not found in system. Please contact support."}
            }

        # 2. Check Local Status
        # We rely on status string. 'Hold', 'Blocked', 'Sold' are considered locked.
        current_status = str(unit.status).strip().title() # Normalize casing
        if current_status not in ["Available"]:
            return {
                "success": False, 
                "status": 400, 
                "payload": {"status": "error", "message": f"Unit is currently {unit.status}"}
            }

        # 3. ERP Synchronization (Middleman Logic)
        is_erp_enabled = bool(getattr(company, "erp_hold_url", False))
        
        if is_erp_enabled:
            # 3a. Check if we already have a pending request for this (prevent double submission)
            if HoldRequestsManagementService._local_sales_request_exists(company, unit):
                return {
                    "success": False,
                    "status": 400,
                    "payload": {"status": "error", "message": "You already have a pending request for this unit."}
                }

            # 3b. Verify Availability on ERP
            # We must ensure it hasn't been sold on the ERP side recently
            erp_check_result = HoldRequestsManagementService._check_and_block_erp(company, unit_code)
            if not erp_check_result["success"]:
                return erp_check_result

        # 4. Update Local Unit
        # We update the status to "Hold" to lock it immediately in our system
        unit.status = "Hold"
        unit.final_price = data.get("final_price")
        unit.save()

        # 5. Normalize Payment Plan
        HoldRequestsManagementService._normalize_payment_plan(
            data=data, 
            project=project, 
            user=user
        )

        # 6. Create Sales Request
        # Note: We now ALWAYS link the local 'unit' object
        sales_request = SalesRequest.objects.create(
            sales_man=user,
            client_id=data.get("client_id"),
            unit=unit,                  # Link local unit
            company=company,
            client_name=client_name,
            project=project,
            final_price=data.get("final_price"),
            client_phone_number=client_phone_number,
            payment_plan_data=data,
        )

        # 7. Notifications (Async)
        # Email
        try:
            threading.Thread(
                target=email_thread_target,
                args=(notify_company_controllers, company, sales_request, data, is_erp_enabled),
            ).start()
        except Exception:
            traceback.print_exc()

        # Pusher
        try:
            payload = HoldRequestsManagementService._build_pusher_payload(company, sales_request)
            threading.Thread(target=send_pusher_notification, args=(payload,)).start()
        except Exception:
            traceback.print_exc()

        return {
            "success": True,
            "status": 200,
            "payload": {"status": "success", "message": "Unit held successfully"}
        }

    # =========================================================
    # INTERNAL: ERP Helpers
    # =========================================================
    @staticmethod
    def _check_and_block_erp(company, unit_code):
        """
        Fetches unit from ERP to check availability, then sends Block command.
        Returns {"success": True} or error dict.
        """
        headers = {}
        if company.erp_hold_url_key:
            headers["Authorization"] = f"Bearer {company.erp_hold_url_key}"

        # A. Fetch Info
        try:
            # Assuming GET /units/{code}
            response = requests.get(
                f"{company.erp_url}{unit_code}", 
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            erp_data = response.json()
            
            # Check Status
            # ✅ Apply same mapping logic (provided_name -> needed_name) BEFORE reading keys
            try:
                custom_map = ERPUnitMappingService.get_mapping_dict(company=company)
                if custom_map:
                    erp_data = apply_header_mapping(erp_data, custom_map)
            except Exception:
                traceback.print_exc()
                # fallback: keep erp_data as-is

            # Check Status (now "status" can be produced by mapping, e.g. availability -> status)
            status = str(
                erp_data.get("status")
                or erp_data.get("availability")     # fallback if ERP still sends this and no mapping exists
                or erp_data.get("Status")           # fallback for title case
                or ""
            ).strip().lower()
            
            
            print(f'status = {status}') 
            if status != "available":
                 return {
                    "success": False,
                    "status": 400,
                    "payload": {"status": "error", "message": f"Unit is {status} on ERP system."}
                }

        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "status": 500,
                "payload": {"status": "error", "message": f"Failed to connect to ERP: {str(e)}"}
            }

        # B. Send Block Command
        post_headers = {"Content-Type": "application/json"}
        if company.erp_hold_url_key:
            post_headers["Authorization"] = f"Bearer {company.erp_hold_url_key}"

        try:
            # Assuming POST /unit/status/update or similar based on existing config
            # Using 'erp_hold_url' from model which usually points to the update endpoint
            
            # Your internal payload (what your code uses)
            payload = {"unit_code": unit_code, "type": "block"}

            # Load mapping: ERP key -> internal key (ced_name -> unit_code)
            external_to_internal = ERPHoldPostMappingService.get_mapping_dict(company=company)

            # Invert it to internal -> ERP key
            internal_to_external = {v: k for k, v in (external_to_internal or {}).items()}

            # Build ERP payload keys
            erp_payload = {}
            for k, v in payload.items():
                erp_key = internal_to_external.get(k, k)   # default keep same key if no mapping
                erp_payload[erp_key] = v
    
    
            block_response = requests.post(
                company.erp_hold_url,
                json=erp_payload,
                headers=post_headers,
                timeout=30
            )
            block_response.raise_for_status()
            
        except Exception as e:
            traceback.print_exc()
            return {
                "success": False,
                "status": 500,
                "payload": {"status": "error", "message": f"Failed to block on ERP: {str(e)}"}
            }

        return {"success": True}

    @staticmethod
    def _local_sales_request_exists(company, unit):
        """
        Check if pending request exists for this specific unit.
        """
        return SalesRequest.objects.filter(
            company=company,
            unit=unit,
            is_approved=False,
            is_fake=False,
        ).exists()

    # =========================================================
    # INTERNAL: Utils
    # =========================================================
    @staticmethod
    def _normalize_payment_plan(*, data, project, user):
        """
        Preserved Logic: Handles One DP vs Multiple DP labels based on config & user rights.
        """
        project_web_config = ProjectWebConfiguration.objects.filter(project=project).first()
        
        has_multiple_dp = bool(project_web_config and project_web_config.has_multiple_dp)
        one_dp_for_sales = bool(project_web_config and project_web_config.one_dp_for_sales)

        is_restricted_client = False
        if user.groups.filter(name__in=["Client", "Sales"]).exists():
            cu = Sales.objects.filter(user=user).first()
            if cu and not cu.can_edit and not cu.can_change_years:
                is_restricted_client = True

        use_multiple_dp_labels = has_multiple_dp
        if one_dp_for_sales and is_restricted_client:
            use_multiple_dp_labels = False

        if use_multiple_dp_labels:
            raw_labels = ["DownPayment1", "DownPayment2"] + [
                f"installment_{i}" for i in range(1, len(data["payments"]) - 1)
            ]
        else:
            raw_labels = ["DownPayment"] + [
                f"installment_{i}" for i in range(1, len(data["payments"]))
            ]

        filtered_payments = []
        filtered_labels = []
        filtered_dates = []
        installment_counter = 1

        for i, p in enumerate(data["payments"]):
            current_date = data["dates"][i] if ("dates" in data and i < len(data["dates"])) else 0

            if p > 0 and current_date != 0:
                if i < len(raw_labels):
                    label = raw_labels[i]
                else:
                    label = f"installment_{installment_counter}"

                if "installment" in label:
                    label = f"installment_{installment_counter}"
                    installment_counter += 1

                filtered_payments.append(p)
                filtered_labels.append(label)
                filtered_dates.append(current_date)

        data["payments"] = filtered_payments
        data["payment_type"] = filtered_labels
        data["dates"] = filtered_dates

        # Recalculate amounts
        try:
            final_p = float(data.get("final_price", 0))
            data["amount"] = [final_p * (float(p) / 100) for p in data["payments"]]
        except (ValueError, TypeError):
            data["amount"] = []

    @staticmethod
    def _build_pusher_payload(company, sales_request):
        display_unit_code = (
            sales_request.unit.unit_code if sales_request.unit else ""
        )
        return {
            "channel": f"company_{company.id}",
            "id": sales_request.id,
            "project_name": sales_request.project.name if sales_request.project else "N/A",
            "sales_man": getattr(sales_request.sales_man, "full_name", None) or "Unknown",
            "client_id": sales_request.client_id or "",
            "client_name": sales_request.client_name or "",
            "client_phone_number": sales_request.client_phone_number or "",
            "unit_code": display_unit_code,
            "discount": sales_request.discount or "",
            "date": sales_request.date.isoformat(),
            "date_display": sales_request.date.strftime("%Y-%m-%d %H:%M"),
            "expiration_date": sales_request.expiration_date.isoformat(),
        }