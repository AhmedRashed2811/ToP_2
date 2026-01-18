# ToP/services/inventory_report_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from django.shortcuts import get_object_or_404

from ..models import Company, Manager

from ..utils.viewer_permissions import is_company_viewer, viewer_company


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class InventoryReportService:
    """
    Service layer for Inventory Dashboard + Inventory Units API.
    - No HttpRequest dependency.
    - Views pass primitives (user, company_id).
    - Preserves original logic (critical).
    """

    # =========================================================
    # Constants
    # =========================================================
    REQUIRED_FIELDS = [
        "city", "project", "unit_type", "area_range", "adj_status",
        "gross_area", "psm", "interest_free_unit_price", "building_type",
        "grace_period_months", "unit_code", "sales_value", "status",
        "reservation_date", "development_delivery_date",
        "contract_delivery_date", "unit_model",
    ]

    # =========================================================
    # Role helpers
    # =========================================================
    
    @staticmethod
    def _is_viewer(user) -> bool:
        return is_company_viewer(user)

    @staticmethod
    def _resolve_viewer_company(user) -> Tuple[Optional[int], Optional[Company]]:
        """
        Viewer behaves like Manager: fixed company from viewer_profile.
        """
        if not InventoryReportService._is_viewer(user):
            return None, None

        c = viewer_company(user)
        if not c:
            return None, None
        return c.id, c


    @staticmethod
    def _is_manager(user) -> bool:
        return user.groups.filter(name="Manager").exists()

    @staticmethod
    def _resolve_manager_company(user) -> Tuple[Optional[int], Optional[Company]]:
        """
        Returns (company_id, company_obj) for Manager, else (None, None).
        Preserves behavior: best effort, silent failure if not found.
        """
        if not InventoryReportService._is_manager(user):
            return None, None

        try:
            rel = Manager.objects.select_related("company").get(user=user)
            return rel.company.id, rel.company
        except Manager.DoesNotExist:
            return None, None

    # =========================================================
    # 1) Dashboard Context
    # =========================================================
    @staticmethod
    def get_inventory_dashboard_context(*, user) -> ServiceResult:
        companies = Company.objects.all()
        company_id, user_company = InventoryReportService._resolve_manager_company(user)
        if not company_id:
            company_id, user_company = InventoryReportService._resolve_viewer_company(user)


        return ServiceResult(
            success=True,
            status=200,
            payload={
                "companies": companies,
                "selected_company_id": company_id,
                "company": user_company,
                "is_viewer": InventoryReportService._is_viewer(user),
            },
        )

    # =========================================================
    # 2) Units API
    # =========================================================
    @staticmethod
    def get_company_units(*, company_id: int, inventory_strategy_factory) -> ServiceResult:
        """
        inventory_strategy_factory: callable(company) -> strategy
        strategy must provide: get_all_units(active_only=False)
        """
        company = get_object_or_404(Company, id=company_id)

        # 1) Delegate fetching to the Strategy (Native vs ERP) (PRESERVED)
        strategy = inventory_strategy_factory(company)

        # We want ALL units (not just active ones), so active_only=False (PRESERVED)
        raw_units = strategy.get_all_units(active_only=False)

        # 2) Normalize + filter fields (PRESERVED)
        filtered_units = InventoryReportService._normalize_units(raw_units)

        return ServiceResult(
            success=True,
            status=200,
            payload={"units": filtered_units},
        )

    # =========================================================
    # Internal: unit normalization
    # =========================================================
    @staticmethod
    def _normalize_units(raw_units) -> List[Dict[str, Any]]:
        filtered_units: List[Dict[str, Any]] = []

        for unit in raw_units:
            item: Dict[str, Any] = {}

            # A) Extract required fields
            for field in InventoryReportService.REQUIRED_FIELDS:
                val = getattr(unit, field, None)
                if val is not None:
                    item[field] = val

            # B) Payment Plan Fallback (PRESERVED)
            pp = getattr(unit, "contract_payment_plan", None) or getattr(unit, "contract_payment_plan", None)
            if pp:
                item["contract_payment_plan"] = pp

            filtered_units.append(item)

        return filtered_units
