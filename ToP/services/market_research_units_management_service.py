# ToP/services/market_research_units_management_service.py

from __future__ import annotations

import csv
import traceback
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, Optional, List, Tuple

import chardet
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction

from ..models import (
    MarketUnitData,
    MarketProject,
    MarketUnitAssetType,
    MarketUnitType,
    MarketUnitFinishingSpec,
)

from ..utils.market_research_units_management_utils import (
    get_user_full_name,
    parse_flexible_date,
    parse_update_endpoint_date,
    clean_numeric_value,
    normalize_csv_row,
    calculate_derived_fields,
)

# put your mapping here (single source of truth)
COLUMN_MAPPING = {
    'Project Name': 'project_name',
    'Project Name ': 'project_name',
    'Developer Name': 'developer_name',
    'Location': 'location',
    'Asset Type': 'asset_type',
    'Unit Type': 'unit_type',
    'BUA': 'bua',
    'Land Area': 'land_area',
    'Garden': 'garden',
    'Unit Price': 'unit_price',
    ' Unit Price ': 'unit_price',
    'PSM': 'psm',
    'Payment yrs raw': 'payment_yrs_raw',
    ' Payment yrs raw ': 'payment_yrs_raw',
    'Payment Yrs': 'payment_yrs',
    'Down Payment': 'down_payment',
    'Down Payment ': 'down_payment',
    'Delivery %': 'delivery_percentage',
    'Cash discount': 'cash_discount',
    'Delivery Date': 'delivery_date',
    'Finishing Specs': 'finishing_specs',
    'Maintenance': 'maintenance',
    'Phase': 'phase',
    'Date of Update': 'date_of_update',
    'Updated by': 'updated_by',
    'Source of info': 'source_of_info',
    'Source of info.': 'source_of_info',
    'Months from Update': 'months_from_update',
    'Notes': 'notes',
    'DP % Range': 'dp_percentage'
}


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trace: Optional[str] = None


class MarketResearchUnitsManagmentService:
    """
    Refactored service layer for market unit data views:
    - list context (pagination + dropdowns)
    - update field(s) / create if id missing
    - create unit (legacy endpoint)
    - delete unit
    - import CSV units
    """

    ALLOWED_PAGE_SIZES = {10, 25, 50, 100}

    NUMERIC_FIELDS_UPDATE = {
        "unit_price", "bua", "land_area", "garden", "down_payment",
        "delivery_percentage", "cash_discount", "maintenance", "phase", "psm"
    }

    LIST_FIELD_NAMES = [
        "project_name", "developer_name", "location", "asset_type", "unit_type", "bua",
        "land_area", "garden", "unit_price", "psm", "payment_yrs", "payment_yrs_raw",
        "down_payment", "delivery_percentage", "cash_discount", "delivery_date",
        "finishing_specs", "maintenance", "phase", "date_of_update",
        "updated_by", "source_of_info", "months_from_update", "notes"
    ]

    # ---------------------------------------------------------
    # 1) LIST PAGE CONTEXT
    # ---------------------------------------------------------
    @staticmethod
    def get_list_context(*, page: Any, page_size: Any) -> ServiceResult:
        try:
            units_list = MarketUnitData.objects.all().order_by("-date_of_update", "id")
            page_size_int = MarketResearchUnitsManagmentService._sanitize_page_size(page_size)

            paginator = Paginator(units_list, page_size_int)
            page_number = page or 1

            try:
                units = paginator.page(page_number)
            except PageNotAnInteger:
                units = paginator.page(1)
            except EmptyPage:
                units = paginator.page(paginator.num_pages)

            projects = MarketProject.objects.select_related("developer", "location").all()
            asset_types = MarketUnitAssetType.objects.all()
            unit_types = MarketUnitType.objects.all()
            finishing_specs = MarketUnitFinishingSpec.objects.all()

            return ServiceResult(
                success=True,
                status=200,
                payload={
                    "units": units,
                    "projects": projects,
                    "asset_types": asset_types,
                    "unit_types": unit_types,
                    "finishing_specs": finishing_specs,
                    "field_names": MarketResearchUnitsManagmentService.LIST_FIELD_NAMES,
                    "page_size": page_size_int,
                }
            )
        except Exception as e:
            return ServiceResult(success=False, status=500, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def _sanitize_page_size(page_size: Any) -> int:
        try:
            ps = int(page_size)
            if ps in MarketResearchUnitsManagmentService.ALLOWED_PAGE_SIZES:
                return ps
            return 25
        except Exception:
            return 25

    # ---------------------------------------------------------
    # 2) UPDATE FIELD(S) (single or bulk, create if id missing)
    # ---------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def update_market_unit(*, user, data: Dict[str, Any]) -> ServiceResult:
        """
        Accepts:
        - single: {id?, field, value}
        - bulk: {id?, fields: {...}}
        """
        try:
            record_id = data.get("id")
            user_full_name = get_user_full_name(user)

            # Single update
            if "field" in data and "value" in data:
                field = data.get("field")
                value = data.get("value")

                unit = MarketResearchUnitsManagmentService._upsert_single(
                    record_id=record_id,
                    field=field,
                    value=value,
                    updated_by=user_full_name,
                )

                derived = MarketResearchUnitsManagmentService._apply_derived(unit)

                return ServiceResult(
                    success=True,
                    status=200,
                    payload={
                        "success": True,
                        "id": unit.id,
                        "display_date": unit.date_of_update.strftime("%b/%y") if field == "date_of_update" else None,
                        **derived
                    }
                )

            # Multiple update
            if "fields" in data and isinstance(data["fields"], dict):
                fields = data["fields"]

                unit = MarketResearchUnitsManagmentService._upsert_many(
                    record_id=record_id,
                    fields=fields,
                    updated_by=user_full_name,
                )

                derived = MarketResearchUnitsManagmentService._apply_derived(unit)

                return ServiceResult(
                    success=True,
                    status=200,
                    payload={
                        "success": True,
                        "id": unit.id,
                        "display_date": unit.date_of_update.strftime("%b/%y") if "date_of_update" in fields else None,
                        **derived
                    }
                )

            return ServiceResult(success=False, status=400, error="Invalid request format")

        except MarketUnitData.DoesNotExist:
            return ServiceResult(success=False, status=404, error="Record not found")
        except ValueError as e:
            return ServiceResult(success=False, status=400, error=str(e))
        except Exception as e:
            return ServiceResult(success=False, status=500, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def _cast_update_value(field: str, value: Any) -> Any:
        # Date parsing for update endpoint
        if field == "date_of_update":
            dt, err = parse_update_endpoint_date(value)
            if err:
                raise ValueError(err)
            return dt

        # Numeric parsing
        if field in MarketResearchUnitsManagmentService.NUMERIC_FIELDS_UPDATE:
            num, err = clean_numeric_value(value, field)
            if err:
                raise ValueError(err)
            return num

        return value

    @staticmethod
    def _upsert_single(*, record_id: Any, field: str, value: Any, updated_by: str) -> MarketUnitData:
        value = MarketResearchUnitsManagmentService._cast_update_value(field, value)

        if not record_id:
            return MarketUnitData.objects.create(**{field: value}, updated_by=updated_by)

        unit = MarketUnitData.objects.get(id=record_id)
        setattr(unit, field, value)
        unit.save()
        return unit

    @staticmethod
    def _upsert_many(*, record_id: Any, fields: Dict[str, Any], updated_by: str) -> MarketUnitData:
        if not record_id:
            first_field, first_value = next(iter(fields.items()))
            unit = MarketUnitData.objects.create(
                **{first_field: MarketResearchUnitsManagmentService._cast_update_value(first_field, first_value)},
                updated_by=updated_by
            )
        else:
            unit = MarketUnitData.objects.get(id=record_id)

        for f, v in fields.items():
            setattr(unit, f, MarketResearchUnitsManagmentService._cast_update_value(f, v))

        unit.save()
        return unit

    @staticmethod
    def _apply_derived(unit: MarketUnitData) -> Dict[str, Any]:
        derived = calculate_derived_fields(unit)
        for k, v in derived.items():
            setattr(unit, k, v)
        unit.save()
        return derived

    # ---------------------------------------------------------
    # 3) CREATE MARKET UNIT (legacy endpoint)
    # ---------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def create_market_unit(*, user, field: str, value: Any) -> ServiceResult:
        try:
            user_full_name = get_user_full_name(user)

            # Cast numeric when needed (matches your create endpoint behavior)
            if field in MarketResearchUnitsManagmentService.NUMERIC_FIELDS_UPDATE:
                num, err = clean_numeric_value(value, field)
                if err:
                    return ServiceResult(success=False, status=400, error=err)
                value = num

            unit = MarketUnitData.objects.create(
                **{field: value},
                updated_by=user_full_name,
                date_of_update=date.today()
            )

            derived = MarketResearchUnitsManagmentService._apply_derived(unit)

            return ServiceResult(
                success=True,
                status=200,
                payload={"success": True, "id": unit.id, **derived}
            )
        except Exception as e:
            return ServiceResult(success=False, status=500, error=str(e), trace=traceback.format_exc())

    # ---------------------------------------------------------
    # 4) DELETE MARKET UNIT
    # ---------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def delete_market_unit(*, record_id: Any) -> ServiceResult:
        try:
            unit = MarketUnitData.objects.get(id=record_id)
            unit.delete()
            return ServiceResult(success=True, status=200, payload={"success": True})
        except MarketUnitData.DoesNotExist:
            return ServiceResult(success=False, status=404, error="Record not found")
        except Exception as e:
            return ServiceResult(success=False, status=400, error=str(e), trace=traceback.format_exc())

    # ---------------------------------------------------------
    # 5) IMPORT CSV
    # ---------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def import_market_units(*, file_bytes: bytes) -> ServiceResult:
        try:
            decoded_lines, enc_error = MarketResearchUnitsManagmentService._decode_csv(file_bytes)
            if enc_error:
                return ServiceResult(success=False, status=400, error=enc_error)

            reader = csv.DictReader(decoded_lines)

            if reader.fieldnames:
                reader.fieldnames = [COLUMN_MAPPING.get(name.strip(), name.strip()) for name in reader.fieldnames]

            imported_count = 0
            error_rows: List[Dict[str, Any]] = []
            row_number = 1

            # Clear existing data (kept as your original)
            MarketUnitData.objects.all().delete()

            numeric_fields = [
                "bua", "land_area", "garden", "unit_price", "psm",
                "down_payment", "delivery_percentage", "cash_discount",
                "maintenance", "phase", "months_from_update"
            ]

            required_fields = ["project_name", "unit_type"]

            for row in reader:
                row_number += 1
                row_errors: List[Any] = []
                processed_row: Dict[str, Any] = {}

                try:
                    row = normalize_csv_row(row, COLUMN_MAPPING)

                    # date_of_update
                    if row.get("date_of_update"):
                        date_obj, error = parse_flexible_date(row["date_of_update"], "date_of_update")
                        if error:
                            row_errors.append(error)
                            processed_row["date_of_update"] = datetime.now().date()
                        else:
                            processed_row["date_of_update"] = date_obj
                    else:
                        processed_row["date_of_update"] = datetime.now().date()

                    # numeric fields
                    for f in numeric_fields:
                        if f in row:
                            val, err = clean_numeric_value(row.get(f), f)
                            if err:
                                row_errors.append(err)
                            processed_row[f] = val

                    # required
                    for f in required_fields:
                        if not row.get(f):
                            row_errors.append({
                                "field": f,
                                "message": "This field is required",
                                "type": "required_field"
                            })
                        else:
                            processed_row[f] = row.get(f)

                    # others
                    for k, v in row.items():
                        if k not in (["date_of_update"] + numeric_fields + required_fields):
                            processed_row[k] = v

                    if row_errors:
                        error_rows.append({"row": row_number, "errors": row_errors, "data": row})
                        continue

                    MarketUnitData.objects.create(
                        project_name=processed_row["project_name"],
                        unit_type=processed_row["unit_type"],
                        developer_name=processed_row.get("developer_name"),
                        location=processed_row.get("location"),
                        asset_type=processed_row.get("asset_type"),
                        bua=processed_row.get("bua"),
                        land_area=processed_row.get("land_area"),
                        garden=processed_row.get("garden"),
                        unit_price=processed_row.get("unit_price"),
                        psm=processed_row.get("psm"),
                        payment_yrs_raw=processed_row.get("payment_yrs_raw"),
                        payment_yrs=processed_row.get("payment_yrs"),
                        down_payment=processed_row.get("down_payment"),
                        delivery_percentage=processed_row.get("delivery_percentage"),
                        cash_discount=processed_row.get("cash_discount"),
                        delivery_date=processed_row.get("delivery_date"),
                        finishing_specs=processed_row.get("finishing_specs"),
                        maintenance=processed_row.get("maintenance"),
                        phase=processed_row.get("phase"),
                        date_of_update=processed_row.get("date_of_update"),
                        updated_by=processed_row.get("updated_by"),
                        source_of_info=processed_row.get("source_of_info"),
                        months_from_update=processed_row.get("months_from_update"),
                        notes=processed_row.get("notes"),
                        dp_percentage=processed_row.get("dp_percentage"),
                    )

                    imported_count += 1

                except Exception as e:
                    error_rows.append({
                        "row": row_number,
                        "errors": [{
                            "message": f"System error: {str(e)}",
                            "type": "system_error"
                        }],
                        "data": row
                    })

            error_summary = MarketResearchUnitsManagmentService._build_error_summary(error_rows)

            return ServiceResult(
                success=True,
                status=200,
                payload={
                    "success": True,
                    "imported_count": imported_count,
                    "total_rows": row_number - 1,
                    "error_count": len(error_rows),
                    "error_summary": error_summary,
                    "error_rows": error_rows[:10],
                    "has_more_errors": len(error_rows) > 10,
                    "sample_error": error_rows[0] if error_rows else None,
                }
            )

        except Exception as e:
            return ServiceResult(success=False, status=500, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def _build_error_summary(error_rows: List[Dict[str, Any]]) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for row in error_rows:
            for err in row.get("errors", []):
                if isinstance(err, dict):
                    t = err.get("type", "general")
                else:
                    t = "general"
                summary[t] = summary.get(t, 0) + 1
        return summary

    @staticmethod
    def _decode_csv(file_bytes: bytes) -> Tuple[Optional[List[str]], Optional[str]]:
        encodings_to_try = [
            "utf-8-sig",
            "utf-8",
            "windows-1256",
            "iso-8859-6",
            "cp1256",
            "cp1252",
            "latin1",
        ]

        decoded = None
        for enc in encodings_to_try:
            try:
                decoded = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if decoded is None:
            detected = chardet.detect(file_bytes).get("encoding")
            return None, f"Failed to decode file. Detected encoding: {detected}. Please save as UTF-8."

        return decoded.splitlines(), None
