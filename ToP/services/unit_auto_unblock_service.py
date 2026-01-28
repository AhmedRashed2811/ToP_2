# ToP/services/unit_auto_unblock_service.py

from __future__ import annotations

import requests
from datetime import timedelta

from django.utils.timezone import localtime, now

from ..models import (
    SalesRequest,
    SalesRequestAnalytical,
    Project,
    ProjectConfiguration,
    ProjectWebConfiguration,
)

from ..services.erp_hold_post_mapping_service import ERPHoldPostMappingService

class UnitAutoUnblockService:
    """
    Handles automatic unblocking of units after the reservation timer expires.
    - Checks against Unit status="Hold".
    - Moves request to Analytical history.
    - Syncs unblock to ERP if connected.
    """

    @staticmethod
    def run() -> str:
        # Fetch active sales requests that are holding a unit
        sales_requests = SalesRequest.objects.select_related("unit", "company").all()

        for sales_request in sales_requests:
            unit = sales_request.unit
            company = sales_request.company

            if not unit or not company:
                continue

            # --- 1. Check Unified Status ---
            # If the unit is not currently in 'Hold' status, we skip it.
            if str(unit.status).strip().lower() != "hold":
                continue

            # --- 2. Load Configuration ---
            project = Project.objects.filter(company=company, name=unit.project).first()
            if not project:
                continue

            config = ProjectConfiguration.objects.filter(project=project).first()
            web_config = ProjectWebConfiguration.objects.filter(project=project).first()

            if not config or not web_config:
                continue

            # --- 3. Check Timer Expiration ---
            local_sales_date = localtime(sales_request.date)
            local_current_time = localtime(now())

            extra_minutes = sales_request.extended_minutes if sales_request.extended_minutes else 0
            total_duration_minutes = web_config.default_timer_in_minutes + extra_minutes

            unlock_threshold = local_sales_date + timedelta(minutes=total_duration_minutes)

            if local_current_time < unlock_threshold:
                continue

            # --- 4. Unblock Logic ---
            
            # A. Update Local Unit
            unit.status = "Available"
            unit.final_price = 0
            unit.discount = 0
            unit.save()

            # B. Sync with ERP (if configured)
            if company.erp_hold_url:
                try:
                    headers = {"Content-Type": "application/json"}
                    if company.erp_hold_url_key:
                        headers["Authorization"] = f"Bearer {company.erp_hold_url_key}"

                    code_to_unblock = unit.unit_code

                    # Internal payload keys (your code keys)
                    payload = {"unit_code": code_to_unblock, "type": "unblock"}

                    # ERP key -> internal key (e.g. "ced_name" -> "unit_code")
                    external_to_internal = ERPHoldPostMappingService.get_mapping_dict(company=company)

                    # Invert to internal -> ERP key
                    internal_to_external = {v: k for k, v in (external_to_internal or {}).items()}

                    # Build mapped ERP payload (keep original key if no mapping exists)
                    erp_payload = {internal_to_external.get(k, k): v for k, v in payload.items()}

                    requests.post(
                        company.erp_hold_url,
                        json=erp_payload,
                        headers=headers,
                        timeout=10  # Short timeout for background task
                    )

                except Exception:
                    # Log error but don't fail the local unblock
                    pass

            # C. Move to Analytical History (Mark as Fake/Expired)
            # FIX: Mapping unit object to unit_code string for Analytical model
            unit_code_str = unit.unit_code if unit else None

            SalesRequestAnalytical.objects.create(
                sales_man=sales_request.sales_man,
                client_id=sales_request.client_id,
                unit_code=unit_code_str, # ✅ Corrected: Pass string, not Object
                date=sales_request.date,
                company=sales_request.company,
                client_name=sales_request.client_name,
                project=sales_request.project,
                final_price=sales_request.final_price,
                discount=sales_request.discount,
                is_approved=False,
                is_fake=True, # Mark as auto-expired/fake
            )

            # D. Delete Active Request
            sales_request.delete()

        return "Auto-unblock check completed."