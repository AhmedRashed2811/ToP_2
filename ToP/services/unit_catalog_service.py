import json
from django.core.serializers.json import DjangoJSONEncoder

from ..models import (
    Company,
    CompanyUser,
    CompanyManager,
    Project,
    UnitPosition,
    UnitPositionChild,
    UnitLayout,
)
from ..strategies.inventory_strategy import get_inventory_strategy


class UnitCatalogService:
    """
    ⚠️ CRITICAL ⚠️
    Phase 2 – Step 1: Structural refactor ONLY.
    Logic and behavior are unchanged.
    """

    # ======================================================
    # PUBLIC ENTRY POINT
    # ======================================================

    @staticmethod
    def build_context(*, user, params):
        user_ctx = UnitCatalogService._resolve_user_context(user, params)
        inventory = UnitCatalogService._build_inventory_payload(
            user_ctx["target_company"],
            user_ctx["is_client"],
        )
        return UnitCatalogService._finalize_context(user_ctx, inventory)

    # ======================================================
    # STEP 1: USER / COMPANY RESOLUTION
    # ======================================================

    @staticmethod
    def _resolve_user_context(user, params):
        units_list = []
        all_companies = []
        user_company = None
        target_company = None

        is_client = user.groups.filter(name="Client").exists()
        is_manager = user.groups.filter(name="Manager").exists()
        is_unbound_user = not (is_client or is_manager)

        if is_client:
            profile = CompanyUser.objects.filter(user=user).first()
            target_company = profile.company if profile else None
            user_company = target_company

        elif is_manager:
            profile = CompanyManager.objects.filter(user=user).first()
            target_company = profile.company if profile else None
            user_company = target_company

        elif is_unbound_user:
            all_companies = list(
                Company.objects.filter(is_active=True).values("id", "name")
            )

            company_id = params.get("company_id")
            if company_id:
                try:
                    target_company = Company.objects.get(id=company_id)
                except Company.DoesNotExist:
                    target_company = None

        return {
            "is_client": is_client,
            "is_manager": is_manager,
            "is_unbound_user": is_unbound_user,
            "user_company": user_company,
            "target_company": target_company,
            "all_companies": all_companies,
        }
        
    # ======================================================
    # STEP 2: INVENTORY AGGREGATION (UNCHANGED LOGIC)
    # ======================================================

    @staticmethod
    def _build_inventory_payload(target_company, is_client):
        units_list = []

        if not target_company:
            return units_list

        # --- A. PRE-FETCH PROJECT MAP ---
        project_map = {
            p.name: p.id for p in Project.objects.filter(company=target_company)
        }

        # --- B. MAP PINS ---
        pin_map = {}

        single_positions = UnitPosition.objects.filter(
            masterplan__project__company=target_company,
            unit_type="single",
        ).values_list("unit_code", flat=True)

        for code in single_positions:
            pin_map[code] = code

        child_positions = UnitPositionChild.objects.filter(
            position__masterplan__project__company=target_company
        ).values("unit_code", "position__unit_code")

        for child in child_positions:
            pin_map[child["unit_code"]] = child["position__unit_code"]

        # --- C. LAYOUT IMAGES ---
        layout_lookup = {}
        all_layouts = UnitLayout.objects.filter(project__company=target_company)

        for layout in all_layouts:
            key = (
                layout.project.name,
                layout.building_type,
                layout.unit_type,
                layout.unit_model,
            )
            if key not in layout_lookup:
                layout_lookup[key] = []
            layout_lookup[key].append(layout.image.url)

        # --- D. FETCH INVENTORY ---
        strategy = get_inventory_strategy(target_company)
        raw_units = strategy.get_all_units(active_only=is_client)

        export_fields = [
            "unit_code",
            "project",
            "building_type",
            "unit_type",
            "unit_model",
            "sellable_area",
            "area_range",
            "status",
            "num_bedrooms",
            "sales_phasing",
            "interest_free_unit_price",
            "development_delivery_date",
            "finishing_specs",
            "garden_area",
            "land_area",
            "penthouse_area",
            "roof_terraces_area",
        ]

        for u in raw_units:
            unit_dict = {}

            for field in export_fields:
                unit_dict[field] = getattr(u, field, None)

            unit_dict["company_name"] = target_company.name

            proj_name = unit_dict.get("project")
            unit_code = unit_dict.get("unit_code")

            unit_dict["project_id"] = project_map.get(proj_name)
            unit_dict["map_focus_code"] = pin_map.get(unit_code)

            layout_key = (
                proj_name,
                unit_dict.get("building_type"),
                unit_dict.get("unit_type"),
                unit_dict.get("unit_model"),
            )
            unit_dict["layout_images"] = layout_lookup.get(layout_key, [])

            units_list.append(unit_dict)

        return units_list

    # ======================================================
    # STEP 3: FINAL CONTEXT ASSEMBLY
    # ======================================================

    @staticmethod
    def _finalize_context(user_ctx, units_list):
        target_company = user_ctx["target_company"]

        return {
            "units_json": json.dumps(units_list, cls=DjangoJSONEncoder),
            "all_companies": user_ctx["all_companies"],
            "is_unbound_user": user_ctx["is_unbound_user"],
            "selected_company_id": target_company.id if target_company else None,
            "company": user_ctx["user_company"],
        }
