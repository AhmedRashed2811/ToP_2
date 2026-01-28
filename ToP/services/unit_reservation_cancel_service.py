from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from django.db import transaction

from ToP.models import (
    Unit,
    Company,
    SalesOperation,
    Admin,
    BusinessAnalysisTeam,
    SalesRequestAnalytical,
    Uploader,
)

from ..utils.google_sheets_utils import cancel_google_sheet_reservation


@dataclass
class AccessContext:
    is_sales_ops: bool
    is_admin_or_biz: bool
    can_access: bool
    sales_ops_company: Optional[Company]
    company: Optional[Company]


@dataclass
class ServiceResult:
    success: bool
    status: int
    message: str
    reason: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    @staticmethod
    def ok(message: str, data: Optional[Dict[str, Any]] = None, status: int = 200) -> "ServiceResult":
        return ServiceResult(True, status, message, None, data)

    @staticmethod
    def fail(message: str, status: int = 400, reason: Optional[str] = None) -> "ServiceResult":
        return ServiceResult(False, status, message, reason, None)


class UnitReservationCancelService:
    """
    Business service:
    - Resolve roles and SalesOperation company.
    - Provide companies list for dropdown (Admin/Business/Superuser).
    - Cancel reservation transactionally (no request object passed).
    """

    # ---------------------------
    # Access / Role Context
    # ---------------------------
    @staticmethod
    def get_access_context(*, actor) -> AccessContext:
        # Treat Django superuser as Admin
        is_superuser = bool(getattr(actor, "is_superuser", False))

        is_sales_ops = SalesOperation.objects.filter(user=actor).exists()
        is_uploader = Uploader.objects.filter(user=actor).exists()
        print(f"is_uploader = {is_uploader}")
        is_admin = is_superuser or Admin.objects.filter(user=actor).exists()
        is_biz = BusinessAnalysisTeam.objects.filter(user=actor).exists()

        sales_ops_company = None
        if is_sales_ops:
            sales_ops = SalesOperation.objects.select_related("company").filter(user=actor).first()
            sales_ops_company = sales_ops.company if sales_ops and sales_ops.company else None
            
        if is_uploader:
            sales_ops = Uploader.objects.select_related("company").filter(user=actor).first()
            sales_ops_company = sales_ops.company if sales_ops and sales_ops.company else None

        can_access = bool(is_uploader or is_sales_ops or is_admin or is_biz)
 
        return AccessContext(
            is_sales_ops=bool(is_sales_ops or is_uploader),
            is_admin_or_biz=bool(is_admin or is_biz),
            can_access=can_access,
            sales_ops_company=sales_ops_company,
            company=sales_ops_company
        )

    # ---------------------------
    # Companies for dropdown
    # ---------------------------
    @staticmethod
    def list_companies_for_dropdown(*, limit: int = 5000) -> List[Company]:
        # No search, so we just return an ordered list.
        # Adjust limit if your DB has huge company count.
        return list(Company.objects.order_by("name")[:limit])

    @staticmethod
    def get_company_by_id(*, company_id: Optional[int]) -> Optional[Company]:
        if not company_id:
            return None
        return Company.objects.filter(id=company_id).first()

    # ---------------------------
    # Cancellation Operation
    # ---------------------------
    @staticmethod
    def cancel_reservation(*, actor, unit_code: str, company: Company) -> ServiceResult:
        unit_code = (unit_code or "").strip()
        if not unit_code:
            return ServiceResult.fail("Unit code is required.", status=400)

        if not company:
            return ServiceResult.fail("Company is required.", status=400)

        try:
            with transaction.atomic():
                unit = (
                    Unit.objects.select_for_update()
                    .filter(unit_code=unit_code, company=company)
                    .first()
                )
                if not unit:
                    return ServiceResult.fail("Unit not found for this company.", status=404)

                # 1) Change Status
                unit.status = "Blocked Cancellation"

                # 2) Clear Reservation Date and Contract Payment Plan
                # reservation_date is DateField => must be None (NULL), not ""
                unit.reservation_date = None
                unit.contract_payment_plan = ""

                # 3) sales_value -> interest_free_unit_price
                restored_price = unit.interest_free_unit_price or 0
                unit.sales_value = restored_price

                unit.save(update_fields=["status", "reservation_date", "contract_payment_plan", "sales_value"])

                # 4) Delete SalesRequestAnalytical for that unit_code scoped by company
                deleted_count, _ = (
                    SalesRequestAnalytical.objects
                    .filter(unit_code=unit_code, company=company)
                    .delete()
                )
                
                if company.has_google_sheets:
                    # Note: Calls to external APIs (Google Sheets) inside a transaction 
                    # will delay the commit. If high performance is needed, 
                    # consider moving this to a background task (Celery).
                    try:
                        cancel_google_sheet_reservation(
                            company=company,
                            unit_code=unit.unit_code,
                            interest_free_price=restored_price
                        )
                    except Exception as e:
                        # Log the error but decide if you want to rollback the DB transaction.
                        # Usually, we allow the DB cancel to succeed even if Sheets fails, 
                        # but we return a warning message.
                        print(f"⚠️ Google Sheet update failed: {e}")
                        # If you want to FAIL the whole operation if Sheet fails, uncomment below:
                        # raise e

                return ServiceResult.ok(
                    "Reservation cancelled successfully.",
                    data={
                        "unit_code": unit.unit_code,
                        "company_id": company.id,
                        "new_status": unit.status,
                        "deleted_sales_requests": deleted_count,
                    },
                    status=200
                )

        except Exception as e:
            return ServiceResult.fail("Operation failed.", status=500, reason=str(e))
