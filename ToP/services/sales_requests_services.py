# ToP/services/sales_request_service.py

import json
import traceback
import threading
import requests  # ✅ Added for direct API calls
from copy import deepcopy
from decimal import Decimal
from datetime import datetime, timedelta
from django.http import HttpResponse
from xhtml2pdf import pisa

from django.db.models import Count
from django.shortcuts import get_object_or_404

from ..models import (
    SalesOperation,
    Manager,
    Sales,
    SalesHead,
    SalesRequest,
    SalesRequestAnalytical,
    Project,
    ProjectWebConfiguration,
    ProjectConfiguration,
    Constraints,
    Unit,
)

from django.template.loader import render_to_string

from ..utils.sales_pdf_utils import (
    build_sales_pdf_rows,
    resolve_actual_unit_code,
    get_unit_details,
)

from ..utils.google_sheets_utils import update_google_sheet_sales_data

from ..utils.notifications_utils import (
    notify_salesman_with_cached_plan,
    notify_company_managers_approval,
    email_thread_target
)


class SalesRequestManagementService:
    """
    Service layer for SalesRequest workflows.
    - Unified Logic: Local DB is Source of Truth.
    - ERP/Google Sheets are synchronization targets based on 'comp_type'.
    """

    # ==================================================
    # INTERNAL HELPERS
    # ==================================================

    @staticmethod
    def _resolve_company_for_user(*, user):
        if user.groups.filter(name="Manager").exists():
            rel = Manager.objects.select_related("company").get(user=user)
            return rel.company

        if user.groups.filter(name__in=["Controller", "SalesOperation"]).exists():
            rel = SalesOperation.objects.select_related("company").get(user=user)
            return rel.company

        # Fallbacks (Admin/Developer)
        rel = SalesOperation.objects.select_related("company").filter(user=user).first()
        if rel:
            return rel.company

        rel = Manager.objects.select_related("company").filter(user=user).first()
        if rel:
            return rel.company

        return None

    @staticmethod
    def _build_erp_headers(company):
        headers = {"Content-Type": "application/json"}
        try:
            if company.erp_url_unit_key:
                headers["Authorization"] = f"Bearer {company.erp_url_unit_key}"
        except Exception:
            pass
        return headers
    
    @staticmethod
    def _is_module_active(company, module_name):
        """Helper to check the new JSON comp_type field safely."""
        if not company or not company.comp_type:
            return False
        # Ensure it's a list and check existence
        types = company.comp_type if isinstance(company.comp_type, list) else []
        return module_name in types

    # ==================================================
    # 1) LIST
    # ==================================================

    @staticmethod
    def get_sales_requests_list_context(*, user, is_impersonating: bool):
        company = SalesRequestManagementService._resolve_company_for_user(user=user)
        if not company:
            return {
                "success": False,
                "error": "No company relationship found for this user (Manager/Controller).",
            }

        # Check if ERP module is active in the list
        erp_system = SalesRequestManagementService._is_module_active(company, "erp")

        sales_requests = (
            SalesRequest.objects.filter(company=company)
            .select_related("sales_man", "unit")
            .order_by("-date")
        )

        major_project = (
            SalesRequest.objects.filter(company=company)
            .values("project")
            .annotate(project_count=Count("project"))
            .order_by("-project_count")
            .first()
        )

        major_project_config = None
        if major_project and major_project.get("project"):
            major_project_obj = Project.objects.filter(id=major_project["project"]).first()
            if major_project_obj:
                major_project_config = ProjectWebConfiguration.objects.filter(
                    project=major_project_obj
                ).first()

        return {
            "success": True,
            "data": {
                "sales_requests": sales_requests,
                "is_impersonating": is_impersonating,
                "erp": erp_system,
                "company": company,
                "major_project_config": major_project_config,
            },
        }

    # ==================================================
    # 2) DELETE (Reject/Cancel)
    # ==================================================

    @staticmethod
    def delete_sales_request(*, user, request_id):
        try:
            sales_request = SalesRequest.objects.select_related("unit", "company", "project", "sales_man").get(id=request_id)
            company = sales_request.company
            unit = sales_request.unit

            # --- 1. LOCAL ACTION: Unblock Unit ---
            if unit:
                # Revert status from "Hold" to "Available"
                # If it was "Sold", be careful, but rejection implies reverting to pool.
                unit.status = "Available"
                unit.final_price = 0
                unit.discount = 0
                unit.save()

            # --- 2. ERP SYNC (If Connected) ---
            # Check comp_type for 'erp' and ensure URL exists
            if SalesRequestManagementService._is_module_active(company, "erp") and company.erp_url_unit:
                headers = SalesRequestManagementService._build_erp_headers(company)
                try:
                    code_to_send = unit.unit_code if unit else ""
                    if code_to_send:
                        # Direct request - Fixed the missing POST execution
                        requests.post(
                            company.erp_url_unit,
                            json={"ced_name": code_to_send, "status_reason": "unblock"},
                            headers=headers,
                            timeout=15
                        )
                except Exception as e:
                    print(f"Failed to unblock unit in ERP: {e}")
                    pass

            # --- 3. ANALYTICAL RECORD ---
            if sales_request.is_approved is False:
                
                # Fix: Extract unit_code string safely
                analytical_unit_code = None
                analytical_base_price = None

                if unit:
                    analytical_unit_code = unit.unit_code
                    # Logic: If Native or Google Sheets is active, we likely track Base Price locally
                    if SalesRequestManagementService._is_module_active(company, "native") or \
                       SalesRequestManagementService._is_module_active(company, "google_sheets"):
                        try:
                            if unit.interest_free_unit_price is not None:
                                analytical_base_price = float(unit.interest_free_unit_price)
                        except Exception:
                            pass
                else:
                    analytical_unit_code = ""

                SalesRequestAnalytical.objects.create(
                    sales_man=sales_request.sales_man,
                    client_id=sales_request.client_id,
                    unit_code=analytical_unit_code,  # ✅ Fixed: Pass string, not Object
                    base_price=analytical_base_price,
                    date=sales_request.date,
                    company=sales_request.company,
                    client_name=sales_request.client_name,
                    project=sales_request.project,
                    final_price=sales_request.final_price,
                    discount=sales_request.discount,
                    is_approved=False,
                    is_fake=True,
                )

            sales_request.delete()

            return {"success": True, "status": 200, "payload": {"status": "success", "message": "Request deleted and unit unlocked."}}

        except SalesRequest.DoesNotExist:
            return {"success": False, "status": 404, "payload": {"status": "error", "message": "Sales Request has been Managed By Another User!"}}
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "status": 500, "payload": {"status": "error", "message": str(e)}}

    # ==================================================
    # 3) APPLY DISCOUNT
    # ==================================================

    @staticmethod
    def apply_discount(*, user, request_id, discount_percentage):
        try:
            sales_request = SalesRequest.objects.select_related("unit").get(id=request_id)
            unit = sales_request.unit

            cached_data = sales_request.payment_plan_data
            if cached_data is None:
                return {
                    "success": False,
                    "status": 400,
                    "payload": {"status": "error", "message": "Critical Error: Original payment plan data is missing."},
                }

            discount_value = float(discount_percentage) / 100.0

            # --- 1. Validation & Config Setup ---
            project = None
            try:
                if unit:
                    project_name = unit.project
                else:
                    project_name = cached_data.get("project_name")
                project = Project.objects.filter(name=project_name).first()
            except Exception:
                pass

            max_discount = 0.0
            discount_on_discount = True

            if project:
                project_configuration = ProjectConfiguration.objects.filter(project=project).first()
                if project_configuration:
                    project_constraints = Constraints.objects.filter(project_config=project_configuration).first()
                    if project_constraints:
                        max_discount = project_constraints.max_exception_discount

                web_config = ProjectWebConfiguration.objects.filter(project=project).first()
                if web_config:
                    discount_on_discount = web_config.discount_after_discount

                if discount_value > max_discount:
                    return {
                        "success": False,
                        "status": 200,
                        "payload": {"status": "error", "message": f"Exception Discount Cannot Exceed {max_discount * 100:.0f}%"},
                    }

                current_stored_discount = sales_request.discount if sales_request.discount else 0.0
                if current_stored_discount > 0:
                    sum_discount = Decimal(str(discount_value)) + Decimal(str(current_stored_discount))
                    if sum_discount > Decimal(str(max_discount)):
                        return {
                            "success": False,
                            "status": 200,
                            "payload": {"status": "error", "message": "Unit Already had its Maximum Exception Discount"},
                        }

            # --- 2. Calculation Helper Variables ---
            try:
                basic_price = float(cached_data.get("basic_price", 0.0))
            except (ValueError, TypeError):
                basic_price = 0.0

            previous_discount = float(sales_request.discount if sales_request.discount else 0.0)
            total_exception_discount = Decimal(str(discount_value)) + Decimal(str(previous_discount))

            old_final_price_ref = 0.0
            new_final_price_ref = 0.0

            # --- 3. Update Logic ---
            # Always attempt to update the local unit first
            if unit:
                current_final = float(unit.final_price)
                old_final_price_ref = current_final

                if previous_discount == 0:
                    price_after_main_discount = current_final
                else:
                    if discount_on_discount:
                        price_after_main_discount = current_final / (1 - previous_discount)
                    else:
                        price_after_main_discount = current_final + (basic_price * previous_discount)

                if discount_on_discount:
                    new_final_price = price_after_main_discount * (1 - float(total_exception_discount))
                else:
                    new_final_price = price_after_main_discount - (basic_price * float(total_exception_discount))

                new_final_price_ref = new_final_price

                unit.discount = float(total_exception_discount)
                unit.final_price = new_final_price
                unit.save()

                sales_request.discount = float(total_exception_discount)
                sales_request.final_price = unit.final_price
                sales_request.save()

                cached_data["final_price"] = unit.final_price

            else:
                # Fallback for data integrity issues (SalesRequest without Unit FK)
                current_final = float(cached_data["final_price"])
                old_final_price_ref = current_final

                if previous_discount == 0:
                    price_after_main_discount = current_final
                else:
                    if discount_on_discount:
                        price_after_main_discount = current_final / (1 - previous_discount)
                    else:
                        price_after_main_discount = current_final + (basic_price * previous_discount)

                if discount_on_discount:
                    new_final_price = price_after_main_discount * (1 - float(total_exception_discount))
                else:
                    new_final_price = price_after_main_discount - (basic_price * float(total_exception_discount))

                new_final_price_ref = new_final_price

                cached_data["final_price"] = new_final_price

                sales_request.discount = float(total_exception_discount)
                sales_request.final_price = cached_data["final_price"]
                sales_request.save()

            # --- 4. Maintenance Fees Scaling ---
            if old_final_price_ref > 0:
                maintenance_scaling_factor = new_final_price_ref / old_final_price_ref
            else:
                maintenance_scaling_factor = 1.0

            updated_maintenance_fees = []
            current_fees_list = cached_data.get("maintenance_fees", [])

            for fee in current_fees_list:
                if fee == "" or fee is None:
                    updated_maintenance_fees.append("")
                else:
                    try:
                        original_fee_val = float(fee)
                        new_fee_val = original_fee_val * maintenance_scaling_factor
                        updated_maintenance_fees.append(new_fee_val)
                    except (ValueError, TypeError):
                        updated_maintenance_fees.append(fee)

            cached_data["maintenance_fees"] = updated_maintenance_fees

            sales_request.payment_plan_data = cached_data
            sales_request.save()

            return {"success": True, "status": 200, "payload": {"status": "success", "message": "Discount Applied Successfully!"}}

        except SalesRequest.DoesNotExist:
            return {"success": False, "status": 404, "payload": {"status": "error", "message": "Sales Request has been Managed By Another User!"}}
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "status": 500, "payload": {"status": "error", "message": str(e)}}

    # ==================================================
    # 4) EXTEND TIMER
    # ==================================================

    @staticmethod
    def extend_sales_request(*, user, request_id, minutes_to_add: int):
        try:
            sales_request = get_object_or_404(SalesRequest, id=request_id)

            max_limit = sales_request.date + timedelta(hours=24)
            current_expiry = sales_request.expiration_date
            new_expiry = current_expiry + timedelta(minutes=minutes_to_add)

            if new_expiry > max_limit:
                remaining_time = max_limit - current_expiry
                remaining_minutes = int(remaining_time.total_seconds() / 60)

                if remaining_minutes <= 0:
                    return {"success": False, "status": 200, "payload": {"status": "error", "message": "Maximum extension limit (24h) reached."}}

                return {
                    "success": False,
                    "status": 200,
                    "payload": {"status": "error", "message": f"Cannot extend that much. You only have {remaining_minutes} minutes left before the 24h cap."},
                }

            sales_request.extended_minutes += minutes_to_add
            sales_request.save()

            return {
                "success": True,
                "status": 200,
                "payload": {
                    "status": "success",
                    "message": f"Extended by {minutes_to_add} minutes",
                    "new_expiry": sales_request.expiration_date.isoformat(),
                },
            }
        except Exception as e:
            return {"success": False, "status": 200, "payload": {"status": "error", "message": str(e)}}

    # ==================================================
    # 5) TIMER STATUS
    # ==================================================

    @staticmethod
    def get_timer_status(*, user):
        active_requests = SalesRequest.objects.filter(is_approved=False, is_fake=False)
        data = {req.id: req.expiration_date.isoformat() for req in active_requests}
        return {"success": True, "status": 200, "payload": data}

    # ==================================================
    # 6) APPROVE (Booking / Contract)
    # ==================================================

    @staticmethod
    def approve_sales_request(
        *,
        user,
        request_id,
        logger=None,
    ):
        try:
            sales_request = SalesRequest.objects.select_related("unit", "company", "project", "sales_man").get(id=request_id)
            company = sales_request.company
            unit = sales_request.unit  # We expect this to be populated now

            cached_data = sales_request.payment_plan_data
            if cached_data is None:
                return {
                    "success": False,
                    "status": 404,
                    "payload": {"status": "error", "message": "Critical Error: Payment Plan data missing from request. Please decline."},
                }

            cached_data = deepcopy(cached_data)

            project_web_config = ProjectWebConfiguration.objects.filter(project=sales_request.project).first()
            is_multiple_dp = bool(project_web_config and project_web_config.has_multiple_dp)
            one_dp_for_sales = bool(project_web_config and project_web_config.one_dp_for_sales)

            raw_payments = cached_data.get("payments", [])
            raw_dates = cached_data.get("dates", [])
            final_price = cached_data.get("final_price", 0)

            # --- LOGIC UPDATE: Determine labels based on Salesman Permissions ---
            sales_man = sales_request.sales_man
            is_restricted_client = False
            
            is_sales = sales_man.groups.filter(name="Sales").exists()
            
            if is_sales:
                sp = Sales.objects.filter(user=sales_man).first()
                if sp and (not sp.can_edit) and (not sp.can_change_years):
                    is_restricted_client = True
                    
                    

            use_multiple_dp_labels = is_multiple_dp
            if one_dp_for_sales and is_restricted_client:
                use_multiple_dp_labels = False

            # Build Labels
            if use_multiple_dp_labels:
                source_labels = ["DownPayment1", "DownPayment2"] + ["installment"] * (len(raw_payments) - 2)
            else:
                source_labels = ["DownPayment"] + ["installment"] * (len(raw_payments) - 1)
            
            filtered_payments = []
            filtered_dates = []
            filtered_labels = []
            installment_counter = 1

            for i, p in enumerate(raw_payments):
                current_date = raw_dates[i] if i < len(raw_dates) else 0

                if p > 0 and current_date != 0:
                    if i < len(source_labels):
                        label = source_labels[i]
                    else:
                        label = f"installment_{installment_counter}"
                        installment_counter += 1

                    if label == "installment":
                        label = f"installment_{installment_counter}"
                        installment_counter += 1

                    filtered_payments.append(p)
                    filtered_dates.append(current_date)
                    filtered_labels.append(label)

            cached_data["payments"] = filtered_payments
            cached_data["dates"] = filtered_dates
            cached_data["payment_type"] = filtered_labels
            cached_data["amount"] = [final_price * (p / 100) for p in filtered_payments]

            # --- NOTIFICATIONS ---
            try:
                threading.Thread(
                    target=email_thread_target,
                    args=(notify_salesman_with_cached_plan, company, sales_request, cached_data),
                ).start()

                threading.Thread(
                    target=email_thread_target,
                    args=(notify_company_managers_approval, company, sales_request, cached_data),
                ).start()
            except Exception:
                traceback.print_exc()

            # Google Sheet Update
            if SalesRequestManagementService._is_module_active(company, "google_sheets"):
                try:
                    update_google_sheet_sales_data(company, sales_request, cached_data)
                except Exception as e:
                    if logger:
                        logger.error(f"Failed to update Google Sheet: {str(e)}")
                    traceback.print_exc()

            # --- 1. LOCAL UPDATE: Update Unit Status ---
            if unit:
                payments_list = cached_data.get("payments", [])
                if payments_list and payments_list[0] == 100:
                    contract_payment_plan = "Cash"
                else:
                    contract_payment_plan = f"{cached_data.get('tenor_years', '')} Yrs"

                unit.status = "Reserved"
                unit.sales_value = cached_data.get("final_price", "")
                unit.contract_payment_plan = contract_payment_plan

                today = datetime.now()
                unit.reservation_date = today.strftime("%Y-%m-%d")
                unit.save()

            # --- 2. ERP SYNC (If Connected) ---
            # Fix: Direct POST execution without relying on passed func
            if SalesRequestManagementService._is_module_active(company, "erp") and company.erp_url:
                headers = {"Content-Type": "application/json"}
                try:
                    if company.erp_url_key:
                        headers["Authorization"] = f"Bearer {company.erp_url_key}"
                except Exception:
                    pass

                try:
                    requests.post(company.erp_url, json=cached_data, headers=headers, timeout=30)
                except Exception as e:
                    print(f"ERP Post Error: {e}")

            # --- 3. ANALYTICAL RECORD ---
            
            analytical_unit_code = None
            analytical_base_price = None

            if unit:
                analytical_unit_code = unit.unit_code
                if SalesRequestManagementService._is_module_active(company, "native") or \
                   SalesRequestManagementService._is_module_active(company, "google_sheets"):
                    try:
                        if unit.interest_free_unit_price is not None:
                            analytical_base_price = float(unit.interest_free_unit_price)
                    except Exception:
                        analytical_base_price = None
            else:
                analytical_unit_code = ""

            SalesRequestAnalytical.objects.create(
                sales_man=sales_request.sales_man,
                client_id=sales_request.client_id,
                unit_code=analytical_unit_code, # ✅ Fixed: Pass string
                base_price=analytical_base_price,
                date=sales_request.date,
                company=sales_request.company,
                client_name=sales_request.client_name,
                project=sales_request.project,
                final_price=sales_request.final_price,
                discount=sales_request.discount,
                is_approved=True,
                is_fake=False,
            )

            sales_request.delete()

            return {"success": True, "status": 200, "payload": {"status": "success", "message": "Request approved and removed."}}

        except SalesRequest.DoesNotExist:
            return {"success": False, "status": 404, "payload": {"status": "error", "message": "Sales Request has been Managed By Another User!"}}
        except Exception as e:
            tb = traceback.format_exc()
            print("🔥 ERROR in approve_sales_request:\n", tb)
            if logger:
                logger.error("ERROR in approve_sales_request:\n%s", tb)
            return {"success": False, "status": 500, "payload": {"status": "error", "message": str(e)}}

    # ==================================================
    # 7) DOWNLOAD SALES PDF
    # ==================================================
    @staticmethod
    def build_sales_pdf_payload(*, request_id: str):
        sales_request = SalesRequest.objects.filter(id=request_id).select_related("unit", "project", "sales_man").first()

        if not sales_request:
            return {
                "success": False,
                "status": 404,
                "error_http": ("Sales Request has been Managed By Another User!", 404),
            }

        data = sales_request.payment_plan_data
        if not data:
            return {
                "success": False,
                "status": 404,
                "error_http": ("No payment plan data found for this unit.", 404),
            }

        actual_unit_code = resolve_actual_unit_code(sales_request)

        computed = build_sales_pdf_rows(data)

        context = {
            "unit_code": (actual_unit_code.split("_")[0] if actual_unit_code else ""),
            "final_price": f"{round(computed['final_price']):,}",
            "currency": computed["currency"],
            "rows": computed["rows"],
            "has_maintenance": computed["has_maintenance"],
            "has_gas": computed["has_gas"],
            "total_maintenance": computed["total_maintenance_str"],
            "total_gas": computed["total_gas_str"],
            "sales_request": sales_request,
            "project_name": sales_request.project.name if sales_request.project else "N/A",
            "client_name": sales_request.client_name or "N/A",
            "client_id": sales_request.client_id or "N/A",
            "client_phone": sales_request.client_phone_number or "N/A",
            "salesman_name": getattr(sales_request.sales_man, "full_name", sales_request.sales_man.email),
            "salesman_email": sales_request.sales_man.email,
            "request_date": sales_request.date.strftime("%Y-%m-%d %H:%M:%S"),
            "company_name": getattr(sales_request.project.company, "name", "N/A") if sales_request.project else "N/A",
            "unit_details": get_unit_details(sales_request),
        }

        html = render_to_string("pdf/sales_request_pdf.html", context)

        filename = f"Sales_Request_{sales_request.client_id}_{actual_unit_code}.pdf"

        return {
            "success": True,
            "status": 200,
            "html": html,
            "filename": filename,
        }

    @staticmethod
    def build_and_render_sales_pdf_response(*, request_id: str) -> HttpResponse:
        result = SalesRequestManagementService.build_sales_pdf_payload(request_id=str(request_id))

        if not result.get("success"):
            msg, code = result.get("error_http", ("Failed to generate PDF", 500))
            return HttpResponse(msg, status=code)

        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{result["filename"]}"'

        pisa_status = pisa.CreatePDF(src=result["html"], dest=response)
        if pisa_status.err:
            return HttpResponse("Failed to generate PDF", status=500)

        return response