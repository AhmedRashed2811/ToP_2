# ToP/services/units_management_service.py

import traceback
from django.db import transaction

from ..models import (
    Unit,
    CompanyManager,
    CompanyController,
    ModificationRecords,
)


class UnitsManagementService:
    """
    Unified service for Unit read + write operations.

    - Includes the previous UnitsQueryService.get_units (unchanged behavior)
    - Includes update_unit logic (preserves your behavior, plus optional safe guard)
    """

    # =====================================================
    # READ: UNITS QUERY
    # =====================================================

    @staticmethod
    def get_units(*, user):
        units_qs = UnitsManagementService._resolve_queryset(user)
        units = UnitsManagementService._serialize_units(units_qs)
        return UnitsManagementService._rename_foreign_keys(units)

    @staticmethod
    def _resolve_queryset(user):
        is_manager = user.groups.filter(name="Manager").exists()
        is_controller = user.groups.filter(name="Controller").exists()

        if is_manager:
            user_manager = CompanyManager.objects.filter(user=user).first()
            return Unit.objects.filter(company=user_manager.company)

        elif is_controller:
            user_controller = CompanyController.objects.filter(user=user).first()
            return Unit.objects.filter(
                company=user_controller.company,
                status__in=["Available", "Contracted", "Reserved"],
            )

        else:
            return Unit.objects.all()

    @staticmethod
    def _serialize_units(units_qs):
        return list(
            units_qs.values(
                "unit_code", "city", "project", "status", "creation_date",
                "contract_date", "delivery_date", "sales_phasing", "construction_phasing",
                "handover_phasing", "phasing", "plot_type", "building_style",
                "building_type", "unit_type", "unit_model", "mirror", "unit_position",
                "building_number", "floor", "sap_code", "num_bedrooms", "num_bathrooms",
                "num_parking_slots", "footprint", "net_area", "sellable_area", "internal_area",
                "covered_terraces", "uncovered_terraces", "penthouse_area", "garage_area",
                "basement_area", "common_area", "roof_pergola_area", "roof_terraces_area",
                "bua", "land_area", "garden_area", "total_area", "net_area_psm",
                "covered_terraces_psm", "uncovered_terraces_psm", "penthouse_psm",
                "garage_psm", "basement_psm", "common_area_psm", "roof_pergola_psm",
                "roof_terraces_psm", "land_psm", "garden_psm", "base_psm", "base_price",
                "cash_price", "final_price", "discount", "maintenance_percent",
                "maintenance_value", "gas", "parking_price", "psm", "sales_value",
                "total_premium_percent", "total_premium_value", "special_premiums",
                "special_discounts", "main_view", "secondary_views", "levels",
                "north_breeze", "corners", "accessibility", "finishing_specs",
                "interest_free_unit_price", "interest_free_psm", "interest_free_years",
                "down_payment_percent", "down_payment", "contract_percent",
                "contract_payment", "delivery_percent", "delivery_payment",
                "club", "blocking_reason", "release_date", "blocking_date",
                "reservation_date", "contract_payment_plan", "contract_value",
                "collected_amount", "collected_percent", "contract_delivery_date",
                "grace_period_months", "construction_delivery_date",
                "development_delivery_date", "client_handover_date", "contractor_type",
                "contractor", "customer", "broker", "bulks", "direct_indirect_sales",
                "area_range", "release_year", "sales_year", "adj_status",
                 "ams",
                "company__name", "project_company__name"
            )
        )

    @staticmethod
    def _rename_foreign_keys(units):
        for unit in units:
            unit["company"] = unit.pop("company__name", None)
            unit["project_company"] = unit.pop("project_company__name", None)
        return units

    # =====================================================
    # WRITE: UPDATE SINGLE FIELD
    # =====================================================

    @staticmethod
    def update_unit_field(*, user, unit_code: str, field: str, value):
        """
        Mirrors your original update_unit view logic:
        - requires unit_code and field and value != None
        - updates setattr(unit, field, value)
        - creates ModificationRecords
        """
        try:
            if not unit_code or not field or value is None:
                return {
                    "success": False,
                    "status": 400,
                    "payload": {"success": False, "error": "Missing required fields"},
                }

            unit = Unit.objects.filter(unit_code=unit_code).first()
            if not unit:
                return {
                    "success": False,
                    "status": 404,
                    "payload": {"success": False, "error": "Unit not found"},
                }

            # Optional: if you want identical behavior to the old view (500 on invalid field),
            # delete this guard and let setattr raise.
            if not hasattr(unit, field):
                return {
                    "success": False,
                    "status": 400,
                    "payload": {"success": False, "error": f"Invalid field: {field}"},
                }

            with transaction.atomic():
                setattr(unit, field, value)
                unit.save()

                ModificationRecords.objects.create(
                    user=user,
                    type="UPDATE",
                    description=f"Updated Unit {unit_code} Set {field} to {value}.",
                )

            return {
                "success": True,
                "status": 200,
                "payload": {"success": True},
            }

        except Exception as e:
            print("❌ Exception in UnitsManagementService.update_unit_field:")
            traceback.print_exc()
            return {
                "success": False,
                "status": 500,
                "payload": {"success": False, "error": str(e)},
            }
