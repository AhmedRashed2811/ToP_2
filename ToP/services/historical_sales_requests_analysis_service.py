# ToP/services/historical_sales_requests_analysis_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.utils.timezone import localtime

from ..models import Company, SalesRequestAnalytical, CompanyType, Unit
from ..utils.historical_sales_requests_analysis_utils import resolve_historical_analysis_scope


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HistoricalSalesRequestsAnalysisService:
    """
    - No HttpRequest dependency.
    - Views pass primitives (user, company_id as int|None).
    - Returns stable JSON payload for AJAX.
    """

    @staticmethod
    def build_page_context(*, user) -> ServiceResult:
        scope = resolve_historical_analysis_scope(user=user)

        if scope.role == "other":
            return ServiceResult(success=False, status=403, error="Not authorized")

        companies = None
        preselected_company = None
        company = None

        if scope.role == "admin_like":
            companies = Company.objects.all().order_by("name")

        if scope.role in ("manager", "sales"):
            preselected_company = scope.company
            company = scope.company

        return ServiceResult(
            success=True,
            status=200,
            payload={
                "scope_role": scope.role,
                "companies": companies,
                "preselected_company": preselected_company,
                "company": company,
            },
        )

    @staticmethod
    def get_approved_rows(*, user, company_id: Optional[int]) -> ServiceResult:
        scope = resolve_historical_analysis_scope(user=user)

        if scope.role == "other":
            return ServiceResult(success=False, status=403, error="Not authorized")

        selected_company: Optional[Company] = None

        if scope.role == "admin_like":
            if not company_id:
                return ServiceResult(success=True, status=200, payload={"success": True, "meta": None, "rows": []})

            selected_company = Company.objects.filter(id=company_id).first()
            if not selected_company:
                return ServiceResult(success=False, status=404, error="Company not found")

        elif scope.role in ("manager", "sales"):
            selected_company = scope.company
            if not selected_company:
                return ServiceResult(success=False, status=404, error="Company not found for this user")

        qs = (
            SalesRequestAnalytical.objects
            .filter(is_approved=True)
            .select_related("sales_man", "company")   # ✅ no unit relation anymore
            .order_by("-date")
        )

        if scope.role == "sales":
            qs = qs.filter(sales_man=user)

        if selected_company:
            qs = qs.filter(company=selected_company)

        # -----------------------------------------------------------
        # NEW LOGIC: Handle Multi-Select Company Type
        # -----------------------------------------------------------
        # Ensure comp_type is a list
        raw_type = selected_company.comp_type if selected_company else []
        comp_type = raw_type if isinstance(raw_type, list) else [raw_type] if raw_type else []

        # Check capabilities based on list membership
        has_erp = 'erp' in comp_type
        has_native = 'native' in comp_type
        has_sheets = 'google_sheets' in comp_type

        # Show base price if it's NOT purely ERP (i.e., has Native or Sheets)
        # or if you simply want to show it whenever those modules are active:
        show_base_price = has_native or has_sheets

        rows: List[Dict[str, Any]] = []
        for r in qs:
            unit_code = (r.unit_code or "")

            base_price = None
            
            # NEW: Initialize unit fields
            land_area = None
            gross_area = None
            
            if show_base_price:
                base_price = float(r.base_price) if r.base_price is not None else None
                
            # Always attempt to fetch Unit details if we have a code and company
            # This allows fetching areas even if base_price is hidden, or vice versa
            if unit_code and selected_company:
                unit_obj = Unit.objects.filter(
                    unit_code=unit_code, 
                    company=selected_company
                ).first()
                
                if unit_obj:
                    land_area = float(unit_obj.land_area) if unit_obj.land_area else 0
                    gross_area = float(unit_obj.gross_area) if unit_obj.gross_area else 0

            sales_price = float(r.final_price) if r.final_price is not None else None

            dt = localtime(r.date) if r.date else None
            date_str = dt.strftime("%d/%m/%Y") if dt else ""
            date_ts = int(dt.timestamp() * 1000) if dt else 0

            rows.append({
                "salesman": getattr(r.sales_man, "full_name", "") if r.sales_man else "",
                "client_id": r.client_id or "",
                "unit_code": unit_code,
                "date": date_str,
                "date_ts": date_ts,
                "base_price": base_price,
                "sales_price": sales_price,
                # ADDED THESE:
                "land_area": land_area,
                "gross_area": gross_area,
            })

        return ServiceResult(
            success=True,
            status=200,
            payload={
                "success": True,
                "meta": {
                    "company_id": selected_company.id if selected_company else None,
                    "company_name": selected_company.name if selected_company else None,
                    "comp_type": comp_type,  # Renamed key as requested
                    "show_base_price": show_base_price,
                },
                "rows": rows,
            },
        )