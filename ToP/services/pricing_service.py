# ToP/services/pricing_service.py

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from ..models import (
    Company,
    Manager,
    PricingCriteria,
    PricingPremiumGroup,
    PricingPremiumSubgroup,
    Project,
    Unit,
)

from ..utils.pricing_utils import (
    DEFAULT_GROUP_TO_FIELD_MAPPING,
    build_unit_values_fields,
    normalize_group_name,
    parse_optional_decimal,
    roundup_to_nearest_ten,
    unit_has_positive_land,
    unit_has_positive_penthouse,
    unit_has_positive_roof,
)


class PricingService:
    """
    Pricing feature service.
    Contains all business logic from:
    - pricing_model
    - get_company_projects
    - get_project_units_simple (units + criteria merge)
    - save_pricing_criteria_view (recalc rules + dependency map)
    - premium groups/subgroups CRUD
    - save unit premium / base price / base psm / premium totals
    """

    # -------------------------
    # Page context
    # -------------------------
    @staticmethod
    def pricing_model_context(*, user) -> Dict[str, Any]:
        companies = Company.objects.all()

        # Same Manager logic as your view:
        company_id = None
        if user.groups.filter(name="Manager").exists():
            manager_profile = Manager.objects.select_related("company").filter(user=user).first()
            if manager_profile and manager_profile.company:
                company_id = manager_profile.company.id

        return {
            "companies": companies,
            "selected_company_id": company_id,
        }

    # -------------------------
    # Projects for company (AJAX)
    # -------------------------
    @staticmethod
    def get_company_projects_payload(company_id: Optional[str]) -> Dict[str, Any]:
        projects: List[Dict[str, Any]] = []
        if company_id:
            try:
                projects = list(Project.objects.filter(company_id=company_id).values("id", "name"))
            except Exception:
                projects = []
        return {"projects": projects}

    # -------------------------
    # Units + criteria merge payload
    # -------------------------
    @staticmethod
    def get_project_units_with_criteria_payload(project_id: Optional[str]) -> Dict[str, Any]:
        units_data: List[Dict[str, Any]] = []

        if not project_id:
            return {"units": units_data}

        try:
            project_obj = Project.objects.get(id=project_id)
            project_name = project_obj.name
            project_company = project_obj.company

            # Units base fields with optional model fields (same logic)
            base_fields = build_unit_values_fields()

            units_queryset = Unit.objects.filter(
                project=project_name,
                company=project_company,
            ).values(*base_fields)
            units_data = list(units_queryset)

            # Pull ALL criteria fields (same list you had, including land)
            criteria_queryset = PricingCriteria.objects.filter(project=project_obj).values(
                "unit_model",
                "bua_price_per_square_meter",
                "extra_bua_percentage",
                "extra_bua_price",
                "terrace_percentage",
                "terrace_price",
                "terrace_area",
                "penthouse_percentage",
                "penthouse_price",
                "extra_penthouse_percentage_per_square_meter",
                "extra_penthouse_price_per_square_meter",
                "roof_percentage",
                "roof_price",
                "extra_roof_percentage_per_square_meter",
                "extra_roof_price_per_square_meter",
                "land_percentage_per_square_meter",
                "land_price_per_square_meter",
                "extra_land_percentage_per_square_meter",
                "extra_land_price_per_square_meter",
            )

            criteria_lookup = {
                c["unit_model"]: c
                for c in criteria_queryset
            }

            # Attach criteria to each unit dict using the same output keys you used
            for unit_dict in units_data:
                unit_model = unit_dict.get("unit_model")
                c = criteria_lookup.get(unit_model, {}) if unit_model else {}

                unit_dict["pricingcriteria__bua_price_per_square_meter"] = c.get("bua_price_per_square_meter")
                unit_dict["pricingcriteria__extra_bua_percentage"] = c.get("extra_bua_percentage")
                unit_dict["pricingcriteria__extra_bua_price"] = c.get("extra_bua_price")

                unit_dict["pricingcriteria__terrace_percentage"] = c.get("terrace_percentage")
                unit_dict["pricingcriteria__terrace_price"] = c.get("terrace_price")
                unit_dict["pricingcriteria__terrace_area"] = c.get("terrace_area")

                unit_dict["pricingcriteria__penthouse_percentage"] = c.get("penthouse_percentage")
                unit_dict["pricingcriteria__penthouse_price"] = c.get("penthouse_price")
                unit_dict["pricingcriteria__extra_penthouse_percentage_per_square_meter"] = c.get(
                    "extra_penthouse_percentage_per_square_meter"
                )
                unit_dict["pricingcriteria__extra_penthouse_price_per_square_meter"] = c.get(
                    "extra_penthouse_price_per_square_meter"
                )

                unit_dict["pricingcriteria__roof_percentage"] = c.get("roof_percentage")
                unit_dict["pricingcriteria__roof_price"] = c.get("roof_price")
                unit_dict["pricingcriteria__extra_roof_percentage_per_square_meter"] = c.get(
                    "extra_roof_percentage_per_square_meter"
                )
                unit_dict["pricingcriteria__extra_roof_price_per_square_meter"] = c.get(
                    "extra_roof_price_per_square_meter"
                )

                unit_dict["pricingcriteria__land_percentage_per_square_meter"] = c.get("land_percentage_per_square_meter")
                unit_dict["pricingcriteria__land_price_per_square_meter"] = c.get("land_price_per_square_meter")
                unit_dict["pricingcriteria__extra_land_percentage_per_square_meter"] = c.get(
                    "extra_land_percentage_per_square_meter"
                )
                unit_dict["pricingcriteria__extra_land_price_per_square_meter"] = c.get(
                    "extra_land_price_per_square_meter"
                )

        except Project.DoesNotExist:
            pass
        except Exception:
            pass

        return {"units": units_data}

    # -------------------------
    # Save Pricing Criteria (core rules preserved)
    # -------------------------
    @staticmethod
    def save_pricing_criteria(*, project_id: str, unit_model: str, field_name: str, field_value_raw: Optional[str]) -> Dict[str, Any]:
        """
        EXACT behavior + recalculation rules:
        - Allowed fields whitelist unchanged
        - Dependent computations unchanged
        - update_fields logic unchanged
        """
        if not all([project_id, unit_model, field_name]):
            return {"success": False, "error": "Missing required data (project_id, unit_model, field_name)."}

        project = get_object_or_404(Project, id=project_id)

        criteria, _created = PricingCriteria.objects.get_or_create(
            project=project,
            unit_model=unit_model,
        )

        # Parse incoming value (same behavior)
        try:
            field_value_to_save = parse_optional_decimal(field_value_raw)
        except (ValueError, InvalidOperation):
            return {"success": False, "error": f"Invalid value for {field_name}. Must be a number."}

        # Whitelist unchanged (including land fields)
        allowed_fields = [
            "bua_price_per_square_meter",
            "extra_bua_percentage",
            "extra_bua_price",
            "terrace_percentage",
            "penthouse_percentage",
            "extra_penthouse_percentage_per_square_meter",
            "roof_percentage",
            "extra_roof_percentage_per_square_meter",
            "land_percentage_per_square_meter",
            "extra_land_percentage_per_square_meter",
        ]
        if field_name not in allowed_fields:
            return {"success": False, "error": f"Field {field_name} is not allowed to be updated via this view."}

        # Save user field
        setattr(criteria, field_name, field_value_to_save)

        # helper booleans (same intent; land flag was computed but not used in your code)
        has_positive_ph = unit_has_positive_penthouse(project, unit_model)
        has_positive_roof = unit_has_positive_roof(project, unit_model)
        _has_positive_land = unit_has_positive_land(project, unit_model)  # kept for parity with your view

        # ---- Recalcs (same triggers and formulas) ----

        # Extra BUA Price = bua * extra_pct
        if field_name in ["bua_price_per_square_meter", "extra_bua_percentage"]:
            bua = getattr(criteria, "bua_price_per_square_meter", None)
            extra_pct = getattr(criteria, "extra_bua_percentage", None)
            if bua is not None and extra_pct is not None:
                criteria.extra_bua_price = bua * extra_pct

        # Terrace Price = ROUNDUP(bua * terr_pct, -1)
        if field_name in ["bua_price_per_square_meter", "terrace_percentage"]:
            bua = getattr(criteria, "bua_price_per_square_meter", None)
            terr_pct = getattr(criteria, "terrace_percentage", None)
            if bua is not None and terr_pct is not None:
                criteria.terrace_price = roundup_to_nearest_ten(bua * terr_pct)

        # Penthouse Price = IF(has_positive_ph, ROUNDUP(bua * ph_pct, -1), 0)
        if field_name in ["bua_price_per_square_meter", "penthouse_percentage"]:
            bua = getattr(criteria, "bua_price_per_square_meter", None)
            ph_pct = getattr(criteria, "penthouse_percentage", None)
            if bua is not None and ph_pct is not None:
                criteria.penthouse_price = roundup_to_nearest_ten(bua * ph_pct) if has_positive_ph else Decimal("0")

        # Extra Penthouse price /m2 = IF(has_positive_ph, ph_price * ep_pct, 0)
        if field_name in ["bua_price_per_square_meter", "penthouse_percentage", "extra_penthouse_percentage_per_square_meter"]:
            ep_pct = getattr(criteria, "extra_penthouse_percentage_per_square_meter", None)
            ph_price = getattr(criteria, "penthouse_price", None)
            if has_positive_ph and ph_price is not None and ep_pct is not None:
                criteria.extra_penthouse_price_per_square_meter = ph_price * ep_pct
            else:
                criteria.extra_penthouse_price_per_square_meter = Decimal("0")

        # Roof Price = IF(has_positive_roof, ROUNDUP(bua * roof_pct, -1), 0)
        if field_name in ["bua_price_per_square_meter", "roof_percentage"]:
            bua = getattr(criteria, "bua_price_per_square_meter", None)
            roof_pct = getattr(criteria, "roof_percentage", None)
            if bua is not None and roof_pct is not None:
                criteria.roof_price = roundup_to_nearest_ten(bua * roof_pct) if has_positive_roof else Decimal("0")

        # Extra Roof Price /m2 = IF(has_positive_roof, roof_price * extra_roof_pct, 0)
        if field_name in ["bua_price_per_square_meter", "roof_percentage", "extra_roof_percentage_per_square_meter"]:
            extra_roof_pct = getattr(criteria, "extra_roof_percentage_per_square_meter", None)
            roof_price = getattr(criteria, "roof_price", None)
            if has_positive_roof and roof_price is not None and extra_roof_pct is not None:
                criteria.extra_roof_price_per_square_meter = roof_price * extra_roof_pct
            else:
                criteria.extra_roof_price_per_square_meter = Decimal("0")

        # Land Price / m2 = ROUNDUP(bua * land_pct, -1)
        if field_name in ["bua_price_per_square_meter", "land_percentage_per_square_meter"]:
            bua = getattr(criteria, "bua_price_per_square_meter", None)
            land_pct = getattr(criteria, "land_percentage_per_square_meter", None)
            if bua is not None and land_pct is not None:
                criteria.land_price_per_square_meter = roundup_to_nearest_ten(bua * land_pct)

        # Extra Land Price / m2 = land_price * extra_land_pct  (no has_positive_land check in your code)
        if field_name in ["bua_price_per_square_meter", "land_percentage_per_square_meter", "extra_land_percentage_per_square_meter"]:
            extra_land_pct = getattr(criteria, "extra_land_percentage_per_square_meter", None)
            land_price = getattr(criteria, "land_price_per_square_meter", None)
            if land_price is not None and extra_land_pct is not None:
                criteria.extra_land_price_per_square_meter = land_price * extra_land_pct
            else:
                criteria.extra_land_price_per_square_meter = Decimal("0")

        # Persist: update_fields logic preserved
        update_fields = {field_name, "updated_at"}

        dependency_map = {
            "bua_price_per_square_meter": [
                "extra_bua_price",
                "terrace_price",
                "penthouse_price",
                "roof_price",
                "land_price_per_square_meter",
                "extra_penthouse_price_per_square_meter",
                "extra_roof_price_per_square_meter",
                "extra_land_price_per_square_meter",
            ],
            "extra_bua_percentage": ["extra_bua_price"],
            "terrace_percentage": ["terrace_price"],
            "penthouse_percentage": ["penthouse_price", "extra_penthouse_price_per_square_meter"],
            "extra_penthouse_percentage_per_square_meter": ["extra_penthouse_price_per_square_meter"],
            "roof_percentage": ["roof_price", "extra_roof_price_per_square_meter"],
            "extra_roof_percentage_per_square_meter": ["extra_roof_price_per_square_meter"],
            "land_percentage_per_square_meter": ["land_price_per_square_meter", "extra_land_price_per_square_meter"],
            "extra_land_percentage_per_square_meter": ["extra_land_price_per_square_meter"],
        }

        for dep in dependency_map.get(field_name, []):
            update_fields.add(dep)

        criteria.save(update_fields=list(update_fields))

        # Response keys preserved
        return {
            "success": True,
            "message": f"Criteria for {unit_model} ({field_name}) saved successfully.",
            "saved_value": str(field_value_to_save) if field_value_to_save is not None else None,
            "extra_bua_price": str(criteria.extra_bua_price) if "extra_bua_price" in update_fields else None,
            "terrace_price": str(criteria.terrace_price) if "terrace_price" in update_fields else None,
            "penthouse_price": str(criteria.penthouse_price) if "penthouse_price" in update_fields else None,
            "extra_penthouse_price_per_square_meter": str(criteria.extra_penthouse_price_per_square_meter)
            if "extra_penthouse_price_per_square_meter" in update_fields else None,
            "roof_price": str(criteria.roof_price) if "roof_price" in update_fields else None,
            "extra_roof_price_per_square_meter": str(criteria.extra_roof_price_per_square_meter)
            if "extra_roof_price_per_square_meter" in update_fields else None,
            "land_price_per_square_meter": str(criteria.land_price_per_square_meter)
            if "land_price_per_square_meter" in update_fields else None,
            "extra_land_price_per_square_meter": str(criteria.extra_land_price_per_square_meter)
            if "extra_land_price_per_square_meter" in update_fields else None,
        }

    # -------------------------
    # Premium groups / subgroups payloads and CRUD
    # -------------------------
    @staticmethod
    def get_premium_groups_payload(project_id: Optional[str]) -> Dict[str, Any]:
        groups_data: List[Dict[str, Any]] = []
        if project_id:
            try:
                groups = (
                    PricingPremiumGroup.objects.filter(project_id=project_id)
                    .prefetch_related("subgroups")
                    .order_by("name")
                )
                for group in groups:
                    groups_data.append({
                        "id": group.id,
                        "name": group.name,
                        "subgroups": [{"id": sg.id, "name": sg.name, "value": sg.value} for sg in group.subgroups.all()],
                    })
            except Exception:
                groups_data = []
        return {"groups": groups_data}

    @staticmethod
    def add_premium_group(*, project_id: str, name: str) -> Dict[str, Any]:
        name = (name or "").strip()
        if not project_id or not name:
            return {"success": False, "error": "Project ID and name are required."}

        project = get_object_or_404(Project, id=project_id)

        if PricingPremiumGroup.objects.filter(project=project, name__iexact=name).exists():
            return {"success": False, "error": "A group with this name already exists for the project."}

        new_group = PricingPremiumGroup.objects.create(name=name, project=project)

        return {
            "success": True,
            "group": {"id": new_group.id, "name": new_group.name, "subgroups": []},
        }

    @staticmethod
    def delete_premium_group(*, group_id: str) -> Dict[str, Any]:
        if not group_id:
            return {"success": False, "error": "Group ID is required."}
        group = get_object_or_404(PricingPremiumGroup, id=group_id)
        group_name = group.name
        group.delete()
        return {"success": True, "message": f'Group "{group_name}" deleted successfully.'}

    @staticmethod
    def add_premium_subgroup(*, group_id: str, name: str, value_str: str) -> Dict[str, Any]:
        name = (name or "").strip()
        value_str = (value_str or "").strip()

        if not group_id or not name or not value_str:
            return {"success": False, "error": "Group ID, name, and value are required."}

        try:
            value = float(value_str)
        except ValueError:
            return {"success": False, "error": "Value must be an integer."}  # matches your exact message

        group = get_object_or_404(PricingPremiumGroup, id=group_id)

        if PricingPremiumSubgroup.objects.filter(premium_group=group, name__iexact=name).exists():
            return {"success": False, "error": "A subgroup with this name already exists in this group."}

        sg = PricingPremiumSubgroup.objects.create(name=name, value=value, premium_group=group)

        return {"success": True, "subgroup": {"id": sg.id, "name": sg.name, "value": sg.value}}

    @staticmethod
    def delete_premium_subgroup(*, subgroup_id: str) -> Dict[str, Any]:
        if not subgroup_id:
            return {"success": False, "error": "Subgroup ID is required."}
        sg = get_object_or_404(PricingPremiumSubgroup, id=subgroup_id)
        sg_name = sg.name
        sg.delete()
        return {"success": True, "message": f'Subgroup "{sg_name}" deleted successfully.'}

    @staticmethod
    def get_project_premium_group_names_payload(project_id: Optional[str]) -> Dict[str, Any]:
        group_names: List[str] = []
        if project_id:
            try:
                groups = PricingPremiumGroup.objects.filter(project_id=project_id).order_by("name")
                group_names = [g.name for g in groups]
            except Exception:
                group_names = []
        return {"group_names": group_names}

    @staticmethod
    def get_project_subgroups_data_payload(project_id: Optional[str]) -> Dict[str, Any]:
        subgroups_data: Dict[str, Any] = {}
        if project_id:
            try:
                groups = (
                    PricingPremiumGroup.objects.filter(project_id=project_id)
                    .prefetch_related("subgroups")
                    .order_by("name")
                )
                for group in groups:
                    subgroups_data[group.name] = [{"id": sg.id, "name": sg.name, "value": sg.value} for sg in group.subgroups.all()]
            except Exception:
                subgroups_data = {}
        return {"subgroups_data": subgroups_data}

    # -------------------------
    # Save selected subgroup name into Unit field (mapping preserved)
    # -------------------------
    @staticmethod
    def save_unit_premium_selection(
        *,
        unit_code: str,
        group_name: str,
        selected_subgroup_name: str,
        mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if not unit_code or not group_name:
            return {"success": False, "error": "Unit code and group name are required."}

        mapping = mapping or DEFAULT_GROUP_TO_FIELD_MAPPING

        normalized = normalize_group_name(group_name)
        target_field = mapping.get(normalized)

        if not target_field:
            return {"success": False, "error": f'No field mapping configured for group "{group_name}".'}

        unit = get_object_or_404(Unit, unit_code=unit_code)
        value_to_set = (selected_subgroup_name or "").strip()
        setattr(unit, target_field, value_to_set if value_to_set else None)
        unit.save(update_fields=[target_field])

        return {
            "success": True,
            "message": f'Subgroup "{value_to_set}" saved for unit "{unit_code}" in field "{target_field}".',
        }

    # -------------------------
    # Save base_price / base_psm / totals (same behavior)
    # -------------------------
    @staticmethod
    def save_unit_base_price(*, unit_code: str, base_price_raw: Optional[str]) -> Dict[str, Any]:
        if not unit_code:
            return {"success": False, "error": "Unit code is required."}

        unit = get_object_or_404(Unit, unit_code=unit_code)

        if base_price_raw and base_price_raw not in ["0", "0.00"]:
            unit.base_price = Decimal(base_price_raw)
        else:
            unit.base_price = None

        unit.save(update_fields=["base_price"])
        return {"success": True, "message": f"Base price updated for unit {unit_code}"}

    @staticmethod
    def save_unit_base_psm(*, unit_code: str, base_psm_raw: Optional[str]) -> Dict[str, Any]:
        if not unit_code:
            return {"success": False, "error": "Unit code is required."}

        unit = get_object_or_404(Unit, unit_code=unit_code)

        if base_psm_raw and base_psm_raw not in ["0", "0.00"]:
            unit.base_psm = Decimal(base_psm_raw)
        else:
            unit.base_psm = None

        unit.save(update_fields=["base_psm"])
        return {"success": True, "message": f"Base PSM updated for unit {unit_code}"}

    @staticmethod
    def save_unit_premium_totals(*, unit_code: str, total_premium_percent_raw: Optional[str], total_premium_value_raw: Optional[str]) -> Dict[str, Any]:
        if not unit_code:
            return {"success": False, "error": "Unit code is required."}

        unit = get_object_or_404(Unit, unit_code=unit_code)

        if total_premium_percent_raw and total_premium_percent_raw not in ["0", "0.00"]:
            unit.total_premium_percent = Decimal(total_premium_percent_raw)
        else:
            unit.total_premium_percent = None

        if total_premium_value_raw and total_premium_value_raw not in ["0", "0.00"]:
            unit.total_premium_value = Decimal(total_premium_value_raw)
        else:
            unit.total_premium_value = None

        unit.save(update_fields=["total_premium_percent", "total_premium_value"])
        return {"success": True, "message": f"Premium totals updated for unit {unit_code}"}
