# ToP/services/sales_performance_service.py

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple

from django.db.models import Min, Max, Q

from ..models import (
    Company,
    CompanyManager,
    Project,
    Unit,
    PricingPremiumSubgroup,
)

from ..utils.sales_performance_utils import (
    PREMIUM_FIELD_MAPPING,
    build_status_counts,
    attach_percentages,
)


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Any] = None
    error: Optional[str] = None
    trace: Optional[str] = None


class SalesPerformanceService:
    """
    Service layer for:
    - sales performance page context
    - company projects list API
    - price range breakdown API
    - unit model breakdown API
    - premium analysis API
    """

    # --------------------------
    # Public endpoints
    # --------------------------
    @staticmethod
    def get_page_context(*, user) -> ServiceResult:
        """
        Preserves your logic:
        - companies = Company.objects.all()
        - if Manager: preselect company_id, attach company, initial_projects
        """
        try:
            companies = Company.objects.all()
            selected_company_id = None
            initial_projects = []
            user_company = None

            if user.groups.filter(name="Manager").exists():
                cm = CompanyManager.objects.filter(user=user).select_related("company").first()
                if cm and cm.company:
                    user_company = cm.company
                    selected_company_id = cm.company.id
                    initial_projects = list(Project.objects.filter(company_id=selected_company_id))

            return ServiceResult(
                success=True,
                status=200,
                payload={
                    "companies": companies,
                    "selected_company_id": selected_company_id,
                    "initial_projects": initial_projects,
                    "company": user_company,
                },
            )
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def get_company_projects(*, request) -> ServiceResult:
        """
        Preserves your logic:
        - read company_id from GET
        - return list of {id, name} for projects in company
        - else return []
        """
        try:
            company_id = request.GET.get("company_id")
            if not company_id:
                return ServiceResult(True, 200, payload=[])

            projects = Project.objects.filter(company_id=company_id).values("id", "name")
            return ServiceResult(True, 200, payload=list(projects))
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def get_sales_analysis_data(*, request) -> ServiceResult:
        """
        Preserves your logic exactly:
        - project_id required
        - units filtered by (company=project_company, project=project_name)
        - exclude interest_free_unit_price__isnull=True
        - compute 5 price ranges based on min/max
        - count statuses within each range and totals
        """
        try:
            project_id = request.GET.get("project_id")
            if not project_id:
                return ServiceResult(False, 400, error="project_id is required")

            project_obj = Project.objects.select_related("company").get(id=project_id)
            project_name = project_obj.name
            project_company = project_obj.company

            units = (
                Unit.objects.filter(company=project_company, project=project_name)
                .exclude(interest_free_unit_price__isnull=True)
            )

            if not units.exists():
                return ServiceResult(True, 200, payload={"price_ranges": [], "totals": {}})

            min_price, max_price = SalesPerformanceService._min_max_price(units)

            # If min/max missing (shouldn’t happen due to exclude null), still protect:
            if min_price is None or max_price is None:
                return ServiceResult(True, 200, payload={"price_ranges": [], "totals": {}})

            price_ranges = SalesPerformanceService._build_price_ranges(
                units=units,
                min_price=min_price,
                max_price=max_price,
                buckets=5,
            )

            totals = SalesPerformanceService._sum_totals(price_ranges)
            attach_percentages(price_ranges, total_all=totals["all"])

            return ServiceResult(True, 200, payload={"price_ranges": price_ranges, "totals": totals})

        except Project.DoesNotExist:
            return ServiceResult(False, 404, error="Project not found")
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def get_sales_analysis_by_unit_model(*, request) -> ServiceResult:
        """
        Preserves your logic:
        - group by distinct unit_model (including null/empty)
        - for each model: counts by status
        - totals + breakdown_percent + released_percent (same formulas)
        """
        try:
            project_id = request.GET.get("project_id")
            if not project_id:
                return ServiceResult(False, 400, error="project_id is required")

            project_obj = Project.objects.select_related("company").get(id=project_id)
            project_name = project_obj.name
            project_company = project_obj.company

            units = Unit.objects.filter(company=project_company, project=project_name)

            if not units.exists():
                return ServiceResult(True, 200, payload={"unit_models": [], "totals": {}})

            unit_models_data: List[Dict[str, Any]] = []
            distinct_models = units.values_list("unit_model", flat=True).distinct()

            for model in distinct_models:
                model_units = units.filter(unit_model=model)
                counts = build_status_counts(model_units)

                unit_models_data.append({
                    "unit_model": model,
                    **counts,
                })

            totals = SalesPerformanceService._sum_totals(unit_models_data)
            attach_percentages(unit_models_data, total_all=totals["all"])

            return ServiceResult(True, 200, payload={"unit_models": unit_models_data, "totals": totals})

        except Project.DoesNotExist:
            return ServiceResult(False, 404, error="Project not found")
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def get_premium_analysis_data(*, request) -> ServiceResult:
        """
        Preserves your logic:
        - premium_type from GET
        - map to field name
        - distinct non-null/non-empty values of that field
        - count statuses
        - lookup premium_percent from PricingPremiumSubgroup:
            subgroup where name=value and premium_group__project=project
        - totals + released_percent
        """
        try:
            project_id = request.GET.get("project_id")
            premium_type = request.GET.get("premium_type")

            if not project_id:
                return ServiceResult(False, 400, error="project_id is required")
            if not premium_type:
                return ServiceResult(False, 400, error="premium_type is required")

            field_name = PREMIUM_FIELD_MAPPING.get(premium_type)
            if not field_name:
                return ServiceResult(False, 400, error="Invalid premium type")

            project = Project.objects.select_related("company").get(id=project_id)
            project_name = project.name
            project_company = project.company

            units = Unit.objects.filter(company=project_company, project=project_name)

            if not units.exists():
                return ServiceResult(True, 200, payload={"premium_groups": [], "totals": {}})

            distinct_values = (
                units.exclude(**{f"{field_name}__isnull": True})
                    .exclude(**{field_name: ""})
                    .values_list(field_name, flat=True)
                    .distinct()
            )

            premium_groups: List[Dict[str, Any]] = []

            for value in distinct_values:
                if not value:
                    continue

                premium_units = units.filter(**{field_name: value})
                counts = build_status_counts(premium_units)

                premium_percent = SalesPerformanceService._get_premium_percent(
                    project=project,
                    premium_value=value,
                )

                premium_groups.append({
                    "premium_value": value,
                    **counts,
                    "premium_percent": premium_percent,
                })

            totals = SalesPerformanceService._sum_totals(premium_groups)

            # Only released_percent was added in your code (no breakdown_percent here)
            for group in premium_groups:
                group["released_percent"] = (group["released"] / totals["all"] * 100) if totals["all"] > 0 else 0

            return ServiceResult(True, 200, payload={"premium_groups": premium_groups, "totals": totals})

        except Project.DoesNotExist:
            return ServiceResult(False, 404, error="Project not found")
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    # --------------------------
    # Private helpers
    # --------------------------
    @staticmethod
    def _min_max_price(units_qs) -> Tuple[Optional[float], Optional[float]]:
        agg = units_qs.aggregate(
            min_price=Min("interest_free_unit_price"),
            max_price=Max("interest_free_unit_price"),
        )
        return agg["min_price"], agg["max_price"]

    @staticmethod
    def _build_price_ranges(*, units, min_price: float, max_price: float, buckets: int = 5) -> List[Dict[str, Any]]:
        # Same math as your view
        range_width = (max_price - min_price) / buckets if buckets else 0
        price_ranges: List[Dict[str, Any]] = []

        current_from = min_price
        for i in range(buckets):
            current_to = current_from + range_width if i < (buckets - 1) else max_price

            range_units = units.filter(
                interest_free_unit_price__gte=current_from,
                interest_free_unit_price__lte=current_to
            )

            counts = build_status_counts(range_units, price_mode=True)

            price_ranges.append({
                "from": current_from,
                "to": current_to,
                **counts,
            })

            # Preserve your exact next-range logic
            current_from = current_to + 1

        return price_ranges

    @staticmethod
    def _sum_totals(rows: List[Dict[str, Any]]) -> Dict[str, int]:
        return {
            "all": sum(r.get("all", 0) for r in rows),
            "released": sum(r.get("released", 0) for r in rows),
            "available": sum(r.get("available", 0) for r in rows),
            "sold_booked": sum(r.get("sold_booked", 0) for r in rows),
        }

    @staticmethod
    def _get_premium_percent(*, project, premium_value: str) -> float:
        subgroup = PricingPremiumSubgroup.objects.filter(
            name=premium_value,
            premium_group__project=project
        ).first()
        return float(subgroup.value) if subgroup else 0.0
