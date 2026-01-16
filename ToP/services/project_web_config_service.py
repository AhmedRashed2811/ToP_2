# ToP/services/project_web_config_service.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from django.db import transaction
from django.shortcuts import get_object_or_404

from ..models import Company, Project, ProjectWebConfiguration
from ..utils.project_web_config_utils import (
    post_bool,
    post_optional_str,
    to_decimal_or_none,
    to_int_or_none,
)


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    redirect_url: Optional[str] = None
    message: Optional[str] = None  # used by views for Django messages


class ProjectWebConfigService:
    """
    Service layer for Project Web Configuration.
    - No HttpRequest dependency.
    - Views pass primitives (project_id, post_dict, payment_schemes_list).
    - Preserves original behavior.
    """

    # ---------------------------------------------------------
    # Fields config (single source of truth)
    # ---------------------------------------------------------
    PAGE_FIELDS = [
        "show_maintenance",
        "show_gas",
        "show_discount",
        "show_payment_frequency",
        "show_payment_scheme",
        "show_currecny",
        "show_lead_name",
        "show_lead_phone_number",
        "show_standerd_price",
        "has_multiple_dp",
        "show_additional_discount",
        "real_discount",
        "show_not_availables_units_for_sales",
        "discount_after_discount",
        "one_dp_for_sales",
    ]

    BOOL_FIELDS = [
        "show_maintenance",
        "show_gas",
        "show_discount",
        "show_payment_frequency",
        "show_payment_scheme",
        "show_currecny",
        "show_lead_name",
        "show_lead_phone_number",
        "discount_after_discount",
        "show_standerd_price",
        "has_multiple_dp",
        "show_additional_discount",
        "real_discount",
        "show_not_availables_units_for_sales",
        "one_dp_for_sales",
    ]

    OPTIONAL_STR_FIELDS = [
        "default_timer_in_minutes",
        "period_between_DPs",
        "period_between_DP_and_intsallment",
    ]

    # =========================================================
    # Public: page context (GET)
    # =========================================================
    @staticmethod
    def get_page_context(*, selected_project_id: Optional[str]) -> ServiceResult:
        companies = Company.objects.all()
        projects = Project.objects.select_related("company").all()

        selected_project = None
        config = None

        if selected_project_id:
            try:
                selected_project = Project.objects.get(id=selected_project_id)
                config = ProjectWebConfiguration.objects.filter(project=selected_project).first()
            except Project.DoesNotExist:
                selected_project = None
                config = None

        return ServiceResult(
            success=True,
            status=200,
            payload={
                "companies": companies,
                "projects": projects,
                "selected_project": selected_project,
                "config": config,
                "years_range": range(1, 13),
                "fields": ProjectWebConfigService.PAGE_FIELDS,
                "payment_scheme_choices": ProjectWebConfiguration.PAYMENT_SCHEME_CHOICES,
            },
        )

    # =========================================================
    # Public: JSON getter (AJAX)
    # =========================================================
    @staticmethod
    def get_config_json(*, project_id: int) -> ServiceResult:
        project = Project.objects.filter(pk=project_id).first()
        if not project:
            return ServiceResult(success=False, status=404, error="Project not found")

        config = ProjectWebConfiguration.objects.filter(project=project).first()
        if not config:
            return ServiceResult(success=True, status=200, payload={"success": True, "config": None})

        return ServiceResult(
            success=True,
            status=200,
            payload={"success": True, "config": ProjectWebConfigService._serialize_config(config)},
        )

    # =========================================================
    # Public: Save (used by BOTH endpoints)
    # - project_web_config (form POST with redirect + message)
    # - save_project_web_config (AJAX POST json response)
    # =========================================================
    @staticmethod
    @transaction.atomic
    def save_config(
        *,
        project_id: int,
        post_dict: Dict[str, Any],
        payment_schemes_list: List[str],
        allowed_years_list: List[str],
        redirect_after_save: bool,
    ) -> ServiceResult:
        project = get_object_or_404(Project, id=project_id)
        config, _ = ProjectWebConfiguration.objects.get_or_create(project=project)

        # Apply POST -> config fields (preserved logic)
        ProjectWebConfigService._apply_post_to_config(
            config=config,
            post_dict=post_dict,
            payment_schemes_list=payment_schemes_list,
            allowed_years_list=allowed_years_list,
        )

        config.save()

        if redirect_after_save:
            return ServiceResult(
                success=True,
                status=200,
                message="✅ Project Web Configuration saved successfully.",
                redirect_url=f"/project_web_config/?project={project.id}",
            )

        return ServiceResult(
            success=True,
            status=200,
            payload={"success": True, "message": "✅ Configuration saved successfully"},
        )

    @staticmethod
    def _clean_allowed_years(raw_list: List[str]) -> List[int]:
        """
        Keep only ints between 1 and 12, unique, sorted.
        """
        years: List[int] = []
        seen = set()

        for item in (raw_list or []):
            try:
                n = int(item)
            except (TypeError, ValueError):
                continue

            if 1 <= n <= 12 and n not in seen:
                seen.add(n)
                years.append(n)

        return sorted(years)


    # =========================================================
    # Internal: apply POST values to config (single place)
    # =========================================================
    @staticmethod
    def _apply_post_to_config(
        *,
        config: ProjectWebConfiguration,
        post_dict: Dict[str, Any],
        payment_schemes_list: List[str],
        allowed_years_list: List[str],
    ) -> None:
        # 1) Boolean fields (same behavior as bool(request.POST.get(...)))
        for field_name in ProjectWebConfigService.BOOL_FIELDS:
            setattr(config, field_name, post_bool(post_dict, field_name))

        # 2) Optional numeric/text fields stored as string-or-None (preserved)
        for field_name in ProjectWebConfigService.OPTIONAL_STR_FIELDS:
            setattr(config, field_name, post_optional_str(post_dict, field_name))

        # 3) Payment schemes list (preserved)
        config.payment_schemes_to_show = payment_schemes_list or []
        
        config.allowed_years_for_sales = ProjectWebConfigService._clean_allowed_years(allowed_years_list)


        # 4) Additional discount logic (preserved)
        # If show_additional_discount is True => parse values; invalid => None
        # else => reset values
        if config.show_additional_discount:
            config.additional_discount = to_decimal_or_none(post_dict.get("additional_discount"))
            config.dp_for_additional_discount = to_int_or_none(post_dict.get("dp_for_additional_discount"))
        else:
            config.additional_discount = None
            config.dp_for_additional_discount = None

    # =========================================================
    # Internal: serializer
    # =========================================================
    @staticmethod
    def _serialize_config(config: ProjectWebConfiguration) -> Dict[str, Any]:
        # Keep it explicit and stable (preserved keys)
        return {
            "show_maintenance": config.show_maintenance,
            "show_gas": config.show_gas,
            "show_discount": config.show_discount,
            "show_payment_frequency": config.show_payment_frequency,
            "show_payment_scheme": config.show_payment_scheme,
            "show_currecny": config.show_currecny,
            "show_lead_name": config.show_lead_name,
            "show_lead_phone_number": config.show_lead_phone_number,
            "show_standerd_price": config.show_standerd_price,
            "has_multiple_dp": config.has_multiple_dp,
            "default_timer_in_minutes": config.default_timer_in_minutes,
            "period_between_DPs": config.period_between_DPs,
            "period_between_DP_and_intsallment": config.period_between_DP_and_intsallment,
            "show_additional_discount": config.show_additional_discount,
            "additional_discount": config.additional_discount,
            "dp_for_additional_discount": config.dp_for_additional_discount,
            "real_discount": config.real_discount,
            "payment_schemes_to_show": config.payment_schemes_to_show,
            "show_not_availables_units_for_sales": config.show_not_availables_units_for_sales,
            "discount_after_discount": config.discount_after_discount,
            "allowed_years_for_sales": config.allowed_years_for_sales or [],
            "one_dp_for_sales": config.one_dp_for_sales,
        }
