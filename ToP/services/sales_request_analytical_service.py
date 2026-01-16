# ToP/services/sales_request_analytical_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple

from django.contrib.auth import get_user_model

from ..models import (
    Company,
    CompanyManager,
    CompanyUser,
    Project,
    SalesRequestAnalytical,
)

User = get_user_model()


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class SalesRequestAnalyticalService:
    """
    Service layer for Sales Dashboard & Analytical APIs.
    - No HttpRequest dependency.
    - Views pass primitives (user, company_id).
    """

    # =========================================================
    # Role helpers
    # =========================================================
    @staticmethod
    def _is_manager(user) -> bool:
        return user.groups.filter(name="Manager").exists()

    @staticmethod
    def _resolve_manager_company(user):
        """
        Manager -> CompanyManager.company
        Returns company or None.
        """
        try:
            rel = CompanyManager.objects.select_related("company").get(user=user)
            return rel.company
        except CompanyManager.DoesNotExist:
            return None

    # =========================================================
    # 1) Sales Dashboard Context
    # =========================================================
    @staticmethod
    def get_sales_dashboard_context(*, user) -> ServiceResult:
        companies = Company.objects.all()

        is_manager = SalesRequestAnalyticalService._is_manager(user)
        user_company = SalesRequestAnalyticalService._resolve_manager_company(user) if is_manager else None

        return ServiceResult(
            success=True,
            status=200,
            payload={
                "companies": companies,
                "is_manager": is_manager,
                "user_company": user_company,
                "company": user_company,  # kept for template compatibility
            },
        )

    # =========================================================
    # 2) Sales Data API
    # =========================================================
    @staticmethod
    def get_sales_data(*, user) -> ServiceResult:
        """
        Preserves behavior:
        - Base queryset is SalesRequestAnalytical with sales_man select_related
        - If Manager: filter by company (best-effort)
        - Return values list
        """
        queryset = SalesRequestAnalytical.objects.select_related("sales_man")

        if SalesRequestAnalyticalService._is_manager(user):
            # Your old code used CompanyUser here, but you used CompanyManager in the dashboard.
            # Best maintainable approach: try CompanyManager first, fallback CompanyUser.
            company = SalesRequestAnalyticalService._resolve_manager_company(user)
            if not company:
                try:
                    cu = CompanyUser.objects.select_related("company").get(user=user)
                    company = cu.company
                except CompanyUser.DoesNotExist:
                    company = None

            if company:
                queryset = queryset.filter(company=company)

        data = list(
            queryset.values(
                "sales_man__full_name",
                "sales_man_id",
                "company_id",
                "project_id",
                "final_price",
                "discount",
                "is_approved",
                "date",
            )
        )

        return ServiceResult(success=True, status=200, payload={"all_sales": data})

    # =========================================================
    # 3) Projects + Salesmen for Company
    # =========================================================
    @staticmethod
    def get_projects_and_salesmen(*, user, company_id: Optional[int]) -> ServiceResult:
        """
        Preserves behavior:
        - company_id from GET unless Manager => override with manager's company
        - projects from Project(company_id)
        - salesmen from User filtered by CompanyUser(company_id)
        """
        # Manager override (preserved intent)
        if SalesRequestAnalyticalService._is_manager(user):
            company = SalesRequestAnalyticalService._resolve_manager_company(user)
            if not company:
                return ServiceResult(success=True, status=200, payload={"projects": [], "salesmen": []})
            company_id = company.id

        if not company_id:
            return ServiceResult(success=True, status=200, payload={"projects": [], "salesmen": []})

        projects = list(Project.objects.filter(company_id=company_id).values("id", "name"))
        salesmen = list(
            User.objects.filter(companyuser__company_id=company_id).values("id", "full_name")
        )

        return ServiceResult(success=True, status=200, payload={"projects": projects, "salesmen": salesmen})
