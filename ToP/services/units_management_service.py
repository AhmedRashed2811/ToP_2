import traceback
from django.db import transaction

from ..models import (
    Unit,
    Manager,
    SalesOperation,
    ModificationRecords,
)


class UnitsManagementService:
    """
    Unified service for Unit read + write operations, with company-scope security.

    - Uploader is treated exactly like Manager (company-scoped)
    - For company-scoped users (Manager/Uploader/SalesOperation/Controller) we DO NOT return "company"
    - update_unit is also company-scoped (prevents editing other company units by guessing unit_code)
    """

    # =====================================================
    # HELPERS: ROLE + COMPANY RESOLUTION
    # =====================================================
    @staticmethod
    def _get_uploader_company(user):
        try:
            return user.uploader_profile.company
        except Exception:
            return None

    @staticmethod
    def _is_manager(user) -> bool:
        return user.groups.filter(name="Manager").exists()

    @staticmethod
    def _is_uploader(user) -> bool:
        # We consider "Uploader" only if it has a linked company profile
        return UnitsManagementService._get_uploader_company(user) is not None

    @staticmethod
    def _is_controller_or_salesops(user) -> bool:
        return user.groups.filter(name__in=["Controller", "SalesOperation"]).exists()

    @staticmethod
    def _is_company_scoped_user(user) -> bool:
        # These users must never receive "company" field in JSON
        return (
            UnitsManagementService._is_manager(user)
            or UnitsManagementService._is_uploader(user)
            or UnitsManagementService._is_controller_or_salesops(user)
        )

    @staticmethod
    def _resolve_company_for_user(user):
        """
        Returns company object for company-scoped users, else None (Admin/Dev/TeamMember).
        """
        if UnitsManagementService._is_manager(user):
            user_manager = Manager.objects.filter(user=user).first()
            return user_manager.company if user_manager else None

        uploader_company = UnitsManagementService._get_uploader_company(user)
        if uploader_company is not None:
            return uploader_company

        if UnitsManagementService._is_controller_or_salesops(user):
            user_ops = SalesOperation.objects.filter(user=user).first()
            return user_ops.company if user_ops else None

        return None

    # =====================================================
    # READ: UNITS QUERY
    # =====================================================
    @staticmethod
    def get_units(*, user):
        units_qs = UnitsManagementService._resolve_queryset(user)
        units = UnitsManagementService._serialize_units(units_qs, user=user)
        units = UnitsManagementService._rename_foreign_keys(units)

        # Hard security: company-scoped users never get "company"
        if UnitsManagementService._is_company_scoped_user(user):
            for u in units:
                if "company" in u:
                    u.pop("company", None)

        return units

    @staticmethod
    def _resolve_queryset(user):
        company = UnitsManagementService._resolve_company_for_user(user)

        # Manager / Uploader: filter by company (no status restriction)
        if UnitsManagementService._is_manager(user) or UnitsManagementService._is_uploader(user):
            return Unit.objects.filter(company=company) if company else Unit.objects.none()

        # Controller / SalesOperation: filter by company + status restriction (your old behavior)
        if UnitsManagementService._is_controller_or_salesops(user):
            return Unit.objects.filter(
                company=company,
                status__in=[
                    "Available",
                    "Contracted",
                    "Reserved",
                    "Hold",
                    "Partner",
                    "Blocked Development",
                    "Blocked Sales",
                ],
            ) if company else Unit.objects.none()

        # Admin/Developer/TeamMember: all units
        return Unit.objects.all()

    @staticmethod
    def _serialize_units(units_qs, *, user):
        """
        Build values list. We only include company__name for non-company-scoped users.
        """
        base_fields = [
            "unit_code", "city", "project", "status", "creation_date",
            "contract_date", "delivery_date", "sales_phasing", "construction_phasing",
            "handover_phasing", "phasing", "plot_type", "building_style",
            "building_type", "unit_type", "unit_model", "mirror", "unit_position",
            "building_number", "floor", "sap_code", "num_bedrooms", "num_bathrooms",
            "num_parking_slots", "footprint", "net_area", "gross_area", "internal_area",
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
            "project_company__name",
        ]

        # Only Admin/Dev/TeamMember get company field
        if not UnitsManagementService._is_company_scoped_user(user):
            base_fields.append("company__name")

        return list(units_qs.values(*base_fields))

    @staticmethod
    def _rename_foreign_keys(units):
        for unit in units:
            # company__name might not exist (company-scoped users)
            if "company__name" in unit:
                unit["company"] = unit.pop("company__name", None)

            unit["project_company"] = unit.pop("project_company__name", None)

        return units

    # =====================================================
    # WRITE: UPDATE SINGLE FIELD
    # =====================================================
    @staticmethod
    def _sales_ops_allowed_fields(user) -> set[str]:
        if not user.groups.filter(name="SalesOperation").exists():
            return set()

        ops = SalesOperation.objects.filter(user=user).only("editable_unit_fields").first()
        raw = (ops.editable_unit_fields or []) if ops else []
        return {str(x).strip() for x in raw if str(x).strip()}

    @staticmethod
    def update_unit_field(*, user, unit_code: str, field: str, value):
        """
        Secure update:
        - company-scoped users can only update units inside their company
        - SalesOperation can update only allowed fields (your existing logic)
        """
        try:
            if not unit_code or not field or value is None:
                return {
                    "success": False,
                    "status": 400,
                    "payload": {"success": False, "error": "Missing required fields"},
                }

            # Company scope enforcement (critical security)
            company = UnitsManagementService._resolve_company_for_user(user)

            unit_qs = Unit.objects.filter(unit_code=unit_code)
            if company is not None:
                unit_qs = unit_qs.filter(company=company)

            unit = unit_qs.first()
            if not unit:
                return {
                    "success": False,
                    "status": 404,
                    "payload": {"success": False, "error": "Unit not found"},
                }

            if not hasattr(unit, field):
                return {
                    "success": False,
                    "status": 400,
                    "payload": {"success": False, "error": f"Invalid field: {field}"},
                }

            with transaction.atomic():

                # SalesOperation: allow only whitelisted fields
                if user.groups.filter(name="SalesOperation").exists():
                    allowed = UnitsManagementService._sales_ops_allowed_fields(user)
                    if field not in allowed:
                        return {
                            "success": False,
                            "status": 403,
                            "payload": {"success": False, "error": f"Field not allowed: {field}"},
                        }

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
