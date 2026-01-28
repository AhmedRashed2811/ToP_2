from typing import List, Dict, Any
from dataclasses import dataclass


from django.db import transaction
from django.core.exceptions import ValidationError

from ..models import Company, Unit, Project, CompanyType
from ..utils.google_sheets_utils import gspread_client, resolve_worksheet
from ..utils.sheet_parsers import (
    get_from_row,
    to_str,
    to_decimal,
    to_date,
)


# =====================================================
# Result DTO
# =====================================================

@dataclass
class InventorySyncResult:
    success: bool
    message: str
    synced_count: int = 0
    deleted_count: int = 0
    row_errors: List[Dict[str, Any]] = None

    def to_dict(self):
        return {
            "success": self.success,
            "message": self.message,
            "synced_count": self.synced_count,
            "deleted_count": self.deleted_count,
            "row_errors": self.row_errors or [],
        }


# =====================================================
# Service
# =====================================================

class InventorySyncService:

    @classmethod
    def sync_company(cls, company: Company) -> InventorySyncResult:

        if not company.google_sheet_url:
            return InventorySyncResult(False, "Missing Google Sheet URL")

        # ---------- Fetch Sheet ----------
        try:
            gc = gspread_client(company)
            sh = gc.open_by_url(company.google_sheet_url)
            ws = resolve_worksheet(
                sh,
                company.google_sheet_gid,
                company.google_sheet_title
            )
            rows = ws.get_all_records()
        except Exception as e:
            return InventorySyncResult(False, f"Google Sheets error: {e}")

        # ---------- Parse Rows ----------
        new_units: List[Unit] = []
        row_errors: List[Dict[str, Any]] = []
        seen_codes = set()

        for idx, row in enumerate(rows, start=2):
            try:
                unit = cls._parse_row(row, company, seen_codes)
                new_units.append(unit)
            except Exception as e:
                row_errors.append({
                    "row": idx,
                    "unit_code": get_from_row(row, ["Unit Code", "UnitCode", "Code"]),
                    "reason": str(e)
                })

        # ---------- Atomic Replace ----------
        try:
            with transaction.atomic():
                qs = Unit.objects.filter(company=company)
                deleted = qs.count()
                qs.delete()
                Unit.objects.bulk_create(new_units, batch_size=1000)
        except Exception as e:
            return InventorySyncResult(False, f"Database error: {e}")

        msg = f"Successfully synced {len(new_units)} units."
        if row_errors:
            msg += f" {len(row_errors)} rows skipped."

        return InventorySyncResult(
            True,
            msg,
            len(new_units),
            deleted,
            row_errors
        )

    # =====================================================
    # Row Parsing (FULL PARITY)
    # =====================================================
 
    @staticmethod
    def _parse_row(
        row: Dict[str, Any],
        company: Company,
        seen_codes: set
    ) -> Unit:
        # -------------------------------
        # Extract Unit Code
        # -------------------------------
        raw_unit_code = get_from_row(
            row,
            ["Unit Code", "UnitCode", "Code", "Unit Code ", "Unit code"]
        )
        unit_code = to_str(raw_unit_code)

        if not unit_code:
            raise ValueError("The 'Unit Code' column is empty.")

        if unit_code in seen_codes:
            raise ValueError(
                f"Duplicate Unit Code '{unit_code}' detected within the sheet."
            )

        seen_codes.add(unit_code)

        # -------------------------------
        # Extract Fields (STRICT PARITY)
        # -------------------------------
        try:
            # String fields
            city = to_str(get_from_row(row, ["City"]))
            project_name = to_str(get_from_row(row, ["Project"]))
            sales_phasing = to_str(get_from_row(row, ["Sales Phasing"]))
            construction_phasing = to_str(get_from_row(row, ["Construction Phasing"]))
            plot_type = to_str(get_from_row(row, ["Plot Type"]))
            building_type = to_str(get_from_row(row, ["Building Type"]))
            unit_type = to_str(get_from_row(row, ["Unit Type"]))
            unit_model = to_str(get_from_row(row, ["Unit Model"]))
            building_number = to_str(get_from_row(row, ["Building Number"]))
            unit_position = to_str(get_from_row(row, ["Unit Number", "Unit Position"]))
            finishing_specs = to_str(
                get_from_row(row, ["Finishing Specs", "Finishing"])
            )
            num_bedrooms = to_str(get_from_row(row, ["Num Bedrooms"]))
            main_view = to_str(get_from_row(row, ["Main View"]))
            secondary_view = to_str(get_from_row(row, ["Secondary View"]))
            levels = to_str(get_from_row(row, ["Levels"]))
            north_breeze = to_str(get_from_row(row, ["North Breeze"]))
            corners = to_str(get_from_row(row, ["Corners"]))
            accessibility = to_str(get_from_row(row, ["Accessibility"]))
            special_premiums = to_str(
                get_from_row(row, ["Special Permiums & Discounts"])
            )
            adj_status = to_str(
                get_from_row(row, ["Adj Status"])
            )
            status = to_str(get_from_row(row, ["Available", "Status"]))
            owner = to_str(get_from_row(row, ["Owner"]))
            contract_payment_plan = to_str(
                get_from_row(row, ["Contract Payment Plan"])
            )
            area_range = to_str(get_from_row(row, ["Area Range"]))

            # Decimal / numeric fields
            internal_area = to_decimal(get_from_row(row, ["Internal Area"]))
            penthouse_area = to_decimal(get_from_row(row, ["Penthouse Area"]))
            bua = to_decimal(get_from_row(row, ["BUA", "B.U.A."]))
            roof_terraces_area = to_decimal(
                get_from_row(row, ["Roof Terraces Area"])
            )
            garden_area = to_decimal(get_from_row(row, ["Garden Area"]))
            land_area = to_decimal(get_from_row(row, ["Land Area"]))
            gross_area = to_decimal(get_from_row(row, ["Gross Area"]))
            interest_free_unit_price = to_decimal(
                get_from_row(row, ["Interest Free Unit Price"])
            )
            sales_value = to_decimal(get_from_row(row, ["Sales Value"]))
            psm = to_decimal(get_from_row(row, ["PSM"]))
            grace_period_months = to_decimal(
                get_from_row(row, ["Grace Period (months)"])
            )

            # Date fields
            development_delivery_date = to_date(
                get_from_row(row, ["Development Delivery Date"])
            )
            reservation_date = to_date(
                get_from_row(row, ["Reservation Date"])
            )
            contract_delivery_date = to_date(
                get_from_row(row, ["Contract Delivery Date"])
            )

        except Exception as format_err:
            raise ValueError(f"Data formatting error: {str(format_err)}")

        # -------------------------------
        # Build Unit kwargs (IDENTICAL)
        # -------------------------------
        unit_kwargs = dict(
            unit_code=unit_code,
            city=city or "",
            project=project_name or "",
            sales_phasing=sales_phasing,
            construction_phasing=construction_phasing,
            plot_type=plot_type,
            building_type=building_type,
            unit_type=unit_type,
            unit_model=unit_model,
            building_number=building_number,
            unit_position=unit_position,
            finishing_specs=finishing_specs,
            num_bedrooms=num_bedrooms,
            main_view=main_view,
            secondary_view=secondary_view,
            levels=levels,
            north_breeze=north_breeze,
            corners=corners,
            accessibility=accessibility,
            special_premiums=special_premiums,
            internal_area=internal_area,
            penthouse_area=penthouse_area,
            land_area=land_area,
            bua=bua,
            roof_terraces_area=roof_terraces_area,
            garden_area=garden_area,
            status=status,
            company=company,
            development_delivery_date=development_delivery_date,
            interest_free_unit_price=interest_free_unit_price,
            contract_payment_plan=contract_payment_plan,
            sales_value=sales_value,
            reservation_date=reservation_date,
            contract_delivery_date=contract_delivery_date,
            grace_period_months=grace_period_months,
            gross_area=gross_area,
            area_range=area_range,
            psm=psm,
            adj_status = adj_status,
            owner =owner,
        )

        # -------------------------------
        # Project linking (IDENTICAL)
        # -------------------------------
        if project_name:
            try:
                proj = Project.objects.filter(name__iexact=project_name).first()
                if proj:
                    unit_kwargs["project_company"] = proj
            except Exception:
                pass

        return Unit(**unit_kwargs)
