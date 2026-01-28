from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Tuple, Set

from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone

from ..models import (
    MarketUnitData,
    MarketProject,
    MarketUnitType,
    MarketUnitAssetType,
    MarketUnitFinishingSpec,
)


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trace: Optional[str] = None


class MarketResearchUnitsManagmentService:
    """
    MarketUnitData CRUD + Import + Derived fields (PSM, payment_yrs, months_from_update).
    Import reads updated_by/date_of_update/months_from_update FROM CSV (no calc).
    """

    # ==============================
    # LIST CONTEXT + PAGINATION
    # ==============================
    @staticmethod
    def get_list_context(*, page: int = 1, page_size: int = 25) -> ServiceResult:
        try:
            page = int(page or 1)
            page_size = int(page_size or 25)
            page_size = max(5, min(200, page_size))
        except Exception:
            page, page_size = 1, 25

        qs = MarketUnitData.objects.all().order_by("-date_of_update", "-id")

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)

        projects = MarketProject.objects.select_related("developer", "location").order_by("name", "id")
        unit_types = MarketUnitType.objects.all().order_by("name")
        asset_types = MarketUnitAssetType.objects.all().order_by("name")
        finishing_specs = MarketUnitFinishingSpec.objects.all().order_by("name")

        return ServiceResult(
            True,
            200,
            payload={
                "page_obj": page_obj,
                "paginator": paginator,
                "page_size": page_size,
                "page_size_options": [10, 25, 50, 100],
                "projects": projects,
                "unit_types": unit_types,
                "asset_types": asset_types,
                "finishing_specs": finishing_specs,
            },
        )

    # ==============================
    # UPDATE SINGLE FIELD (AJAX)
    # ==============================
    @staticmethod
    @transaction.atomic
    def update_market_unit(*, user, data: Dict[str, Any]) -> ServiceResult:
        try:
            record_id = data.get("id")
            field = (data.get("field") or "").strip()
            value = data.get("value")

            if not record_id or not field:
                return ServiceResult(False, 400, error="Missing id or field")

            unit = MarketUnitData.objects.filter(id=record_id).first()
            if not unit:
                return ServiceResult(False, 404, error="Record not found")

            old_project = unit.project_name
            old_unit_type = unit.unit_type

            readonly_fields = {
                "psm", "payment_yrs", "months_from_update",
                "updated_by", "developer_name", "location"
            }
            if field in readonly_fields:
                return ServiceResult(True, 200, payload={"success": True, "skipped": True})

            # Project dropdown: value is MarketProject.id or name
            if field == "project_name":
                project = MarketResearchUnitsManagmentService._get_project_from_value(value)
                if not project:
                    return ServiceResult(False, 400, error="Invalid project selected")

                unit.project_name = project.name
                unit.developer_name = project.developer.name if project.developer else ""
                unit.location = project.location.name if project.location else ""

            elif field in {"unit_type", "asset_type", "finishing_specs"}:
                unit.__dict__[field] = MarketResearchUnitsManagmentService._normalize_text(value)

            elif field == "date_of_update":
                unit.date_of_update = MarketResearchUnitsManagmentService._parse_date(value)

            elif field in {
                "bua", "land_area", "garden", "unit_price", "down_payment",
                "delivery_percentage", "cash_discount", "maintenance", "phase"
            }:
                unit.__dict__[field] = MarketResearchUnitsManagmentService._parse_float(value)

            elif field in {"payment_yrs_raw", "delivery_date", "source_of_info", "notes", "dp_percentage", "offering"}:
                unit.__dict__[field] = value if value is not None else ""

            else:
                return ServiceResult(False, 400, error=f"Unknown field: {field}")

            # Always update updated_by on any change
            unit.updated_by = MarketResearchUnitsManagmentService._user_full_name(user)

            # Recompute derived fields on edits
            MarketResearchUnitsManagmentService._recompute_row(
                unit,
                compute_psm=True,
                compute_months=True,   # editable path: compute
                compute_payment=True
            )

            unit.save()

            # payment group changes -> recompute group payment_yrs
            group_updates = []
            if field in {"payment_yrs_raw", "unit_type", "project_name"}:
                if old_project and old_unit_type:
                    MarketResearchUnitsManagmentService._recompute_payment_yrs_group(old_project, old_unit_type)
                if unit.project_name and unit.unit_type:
                    MarketResearchUnitsManagmentService._recompute_payment_yrs_group(unit.project_name, unit.unit_type)
                    group_updates = MarketResearchUnitsManagmentService._get_group_payment_yrs(unit.project_name, unit.unit_type)

            return ServiceResult(
                True,
                200,
                payload={
                    "success": True,
                    "id": unit.id,
                    "computed": MarketResearchUnitsManagmentService._row_computed_payload(unit),
                    "group_updates": group_updates,
                },
            )
        except Exception as e:
            return ServiceResult(False, 500, error="Update failed", trace=str(e))

    # ==============================
    # CREATE UNIT (FROM MODAL DATA)
    # ==============================
    @staticmethod
    @transaction.atomic
    def create_market_unit(*, user, data: Dict[str, Any]) -> ServiceResult:
        """
        Create using full payload from modal (AJAX).
        Developer/location are derived from project selection.
        PSM/payment_yrs/months_from_update computed.
        """
        try:
            unit = MarketUnitData()

            # project id/name
            project = MarketResearchUnitsManagmentService._get_project_from_value(data.get("project_name"))
            if project:
                unit.project_name = project.name
                unit.developer_name = project.developer.name if project.developer else ""
                unit.location = project.location.name if project.location else ""
            else:
                # allow blank / unknown
                unit.project_name = MarketResearchUnitsManagmentService._normalize_text(data.get("project_name"))
                unit.developer_name = ""
                unit.location = ""

            # dropdowns
            unit.asset_type = MarketResearchUnitsManagmentService._normalize_text(data.get("asset_type"))
            unit.unit_type = MarketResearchUnitsManagmentService._normalize_text(data.get("unit_type"))
            unit.finishing_specs = MarketResearchUnitsManagmentService._normalize_text(data.get("finishing_specs"))

            # numbers
            unit.bua = MarketResearchUnitsManagmentService._parse_float(data.get("bua"))
            unit.land_area = MarketResearchUnitsManagmentService._parse_float(data.get("land_area"))
            unit.garden = MarketResearchUnitsManagmentService._parse_float(data.get("garden"))
            unit.unit_price = MarketResearchUnitsManagmentService._parse_float(data.get("unit_price"))

            unit.payment_yrs_raw = (data.get("payment_yrs_raw") or "").strip()
            unit.down_payment = MarketResearchUnitsManagmentService._parse_float(data.get("down_payment"))
            unit.delivery_percentage = MarketResearchUnitsManagmentService._parse_float(data.get("delivery_percentage"))
            unit.cash_discount = MarketResearchUnitsManagmentService._parse_float(data.get("cash_discount"))

            unit.delivery_date = (data.get("delivery_date") or "").strip()
            unit.maintenance = MarketResearchUnitsManagmentService._parse_float(data.get("maintenance"))
            unit.phase = MarketResearchUnitsManagmentService._parse_float(data.get("phase"))

            unit.date_of_update = MarketResearchUnitsManagmentService._parse_date(data.get("date_of_update"))
            unit.source_of_info = data.get("source_of_info") or ""
            unit.dp_percentage = data.get("dp_percentage") or ""
            unit.notes = data.get("notes") or ""
            unit.offering = data.get("offering") or ""

            # system
            unit.updated_by = MarketResearchUnitsManagmentService._user_full_name(user)

            MarketResearchUnitsManagmentService._recompute_row(
                unit,
                compute_psm=True,
                compute_months=True,
                compute_payment=True
            )

            unit.save()

            # recompute group payment_yrs for this group
            if unit.project_name and unit.unit_type:
                MarketResearchUnitsManagmentService._recompute_payment_yrs_group(unit.project_name, unit.unit_type)

            return ServiceResult(True, 200, payload={"success": True, "id": unit.id})
        except Exception as e:
            return ServiceResult(False, 500, error="Create failed", trace=str(e))

    # ==============================
    # DELETE SINGLE
    # ==============================
    @staticmethod
    @transaction.atomic
    def delete_market_unit(*, record_id: Any) -> ServiceResult:
        try:
            if not record_id:
                return ServiceResult(False, 400, error="Missing id")

            unit = MarketUnitData.objects.filter(id=record_id).first()
            if not unit:
                return ServiceResult(False, 404, error="Record not found")

            unit.delete()
            return ServiceResult(True, 200, payload={"success": True})
        except Exception as e:
            return ServiceResult(False, 500, error="Delete failed", trace=str(e))

    # ==============================
    # CLEAR ALL (ADVANCED CONFIRM)
    # ==============================
    @staticmethod
    @transaction.atomic
    def clear_all_market_units(*, confirm_text: str) -> ServiceResult:
        try:
            if (confirm_text or "").strip() != "Accept Delete All":
                return ServiceResult(False, 400, error='Confirmation text must be exactly: "Accept Delete All"')

            deleted_count = MarketUnitData.objects.all().count()
            MarketUnitData.objects.all().delete()

            return ServiceResult(True, 200, payload={"success": True, "deleted": deleted_count})
        except Exception as e:
            return ServiceResult(False, 500, error="Clear all failed", trace=str(e))

    # ==============================
    # IMPORT CSV (UPDATED)
    # ==============================
    @staticmethod
    @transaction.atomic
    def import_market_units(*, user, file_bytes: bytes) -> ServiceResult:
        """
        Import notes:
        - updated_by, date_of_update, months_from_update are read from CSV (NO CALC)
        - project matching is normalized and case-insensitive, and saved using canonical DB name
        - PSM/payment_yrs can remain computed
        - still skips repeated header rows
        - upsert (update if exists else create)
        """
        decoded_lines, decode_err = MarketResearchUnitsManagmentService._decode_csv_bytes(file_bytes)
        if decoded_lines is None:
            return ServiceResult(False, 400, error=decode_err or "Unsupported file encoding. Export as CSV UTF-8.")

        decoded_lines = [ln for ln in decoded_lines if ln and ln.strip()]

        try:
            sample = "\n".join(decoded_lines[:10])
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            reader = csv.DictReader(decoded_lines, dialect=dialect)
        except Exception:
            reader = csv.DictReader(decoded_lines)

        # Build normalized project map once
        all_projects = list(MarketProject.objects.select_related("developer", "location").all())
        project_map = {MarketResearchUnitsManagmentService._project_key(p.name): p for p in all_projects}

        created = 0
        updated = 0
        skipped = 0
        touched_groups: Set[Tuple[str, str]] = set()

        for raw_row in reader:
            row = MarketResearchUnitsManagmentService._canonicalize_row(raw_row)

            # skip repeated header rows
            if MarketResearchUnitsManagmentService._row_looks_like_header(row):
                skipped += 1
                continue

            raw_project = row.get("project_name")
            project_name_in = MarketResearchUnitsManagmentService._normalize_text(raw_project)
            project_key = MarketResearchUnitsManagmentService._project_key(project_name_in)

            project_obj = project_map.get(project_key)
            if not project_obj and project_name_in:
                # fallback db lookup (still normalized)
                project_obj = MarketProject.objects.select_related("developer", "location").filter(name__iexact=project_name_in).first()

            # canonical project name (if found)
            project_name = project_obj.name if project_obj else project_name_in

            unit_type = MarketResearchUnitsManagmentService._normalize_text(row.get("unit_type"))
            asset_type = MarketResearchUnitsManagmentService._normalize_text(row.get("asset_type"))
            finishing_specs = MarketResearchUnitsManagmentService._normalize_text(row.get("finishing_specs"))

            bua = MarketResearchUnitsManagmentService._parse_float(row.get("bua"))
            unit_price = MarketResearchUnitsManagmentService._parse_float(row.get("unit_price"))
            payment_yrs_raw = (row.get("payment_yrs_raw") or "").strip()

            if not (project_name or unit_type or bua or unit_price):
                skipped += 1
                continue

            developer_name = project_obj.developer.name if project_obj and project_obj.developer else ""
            location_name = project_obj.location.name if project_obj and project_obj.location else ""

            # Upsert key (keep as-is from your current logic)
            down_payment = MarketResearchUnitsManagmentService._parse_float(row.get("down_payment"))
            delivery_date = (row.get("delivery_date") or "").strip()
            payment_raw = payment_yrs_raw

            existing = MarketUnitData.objects.filter(
                project_name__iexact=project_name,
                unit_type__iexact=unit_type,
                bua=bua,
                unit_price=unit_price,
                down_payment=down_payment,
                delivery_date=delivery_date,
                payment_yrs_raw=payment_raw,
            ).first()

            if existing:
                unit = existing
                updated += 1
            else:
                unit = MarketUnitData()
                created += 1

            # Assign imported fields
            unit.project_name = project_name
            unit.developer_name = developer_name
            unit.location = location_name

            unit.asset_type = asset_type
            unit.unit_type = unit_type
            unit.finishing_specs = finishing_specs

            unit.bua = bua
            unit.land_area = MarketResearchUnitsManagmentService._parse_float(row.get("land_area"))
            unit.garden = MarketResearchUnitsManagmentService._parse_float(row.get("garden"))
            unit.unit_price = unit_price

            unit.payment_yrs_raw = payment_raw
            unit.down_payment = down_payment
            unit.delivery_percentage = MarketResearchUnitsManagmentService._parse_float(row.get("delivery_percentage"))
            unit.cash_discount = MarketResearchUnitsManagmentService._parse_float(row.get("cash_discount"))

            unit.delivery_date = delivery_date
            unit.maintenance = MarketResearchUnitsManagmentService._parse_float(row.get("maintenance"))
            unit.phase = MarketResearchUnitsManagmentService._parse_float(row.get("phase"))

            # ✅ read date_of_update from CSV
            unit.date_of_update = MarketResearchUnitsManagmentService._parse_date(row.get("date_of_update"))

            unit.source_of_info = row.get("source_of_info") or ""
            unit.notes = row.get("notes") or ""
            unit.offering = row.get("offering") or ""
            unit.dp_percentage = row.get("dp_percentage") or ""

            # ✅ read updated_by from CSV (no override) - fallback to current user if empty
            csv_updated_by = MarketResearchUnitsManagmentService._normalize_text(row.get("updated_by"))
            unit.updated_by = csv_updated_by if csv_updated_by else MarketResearchUnitsManagmentService._user_full_name(user)

            # ✅ read months_from_update from CSV (no calc) - if provided
            csv_months = MarketResearchUnitsManagmentService._parse_int(row.get("months_from_update"))
            if csv_months is not None:
                unit.months_from_update = csv_months

            # Recompute derived fields:
            # - PSM: yes
            # - payment_yrs: yes (group-based)
            # - months_from_update: ONLY if CSV didn't provide it
            MarketResearchUnitsManagmentService._recompute_row(
                unit,
                compute_psm=True,
                compute_payment=True,
                compute_months=(csv_months is None),
            )

            unit.save()

            if unit.project_name and unit.unit_type:
                touched_groups.add((unit.project_name, unit.unit_type))

        # recompute payment_yrs for touched groups
        for project_name, unit_type in touched_groups:
            MarketResearchUnitsManagmentService._recompute_payment_yrs_group(project_name, unit_type)

        return ServiceResult(True, 200, payload={"success": True, "created": created, "updated": updated, "skipped": skipped})

    # ======================================================
    # INTERNALS
    # ======================================================
    @staticmethod
    def _user_full_name(user) -> str:
        if not user:
            return ""
        full_name = getattr(user, "full_name", None)
        if full_name:
            return str(full_name).strip()
        try:
            gn = user.get_full_name()
            if gn:
                return gn.strip()
        except Exception:
            pass
        return getattr(user, "username", "") or "Unknown"

    @staticmethod
    def _normalize_text(raw: Any) -> str:
        if raw is None:
            return ""
        s = str(raw)
        s = s.replace("\ufeff", "").replace("\u200f", "").replace("\u200e", "")
        s = unicodedata.normalize("NFKC", s)
        s = re.sub(r"[\u0640\u064b-\u065f\u0670]", "", s)  # tatweel + tashkeel
        s = re.sub(r"\s+", " ", s, flags=re.UNICODE).strip()
        return s

    @staticmethod
    def _project_key(name: str) -> str:
        """
        Strong normalization for project matching (csv vs db):
        - strip, lower, remove punctuation
        - remove leading "project"/"مشروع"
        """
        s = MarketResearchUnitsManagmentService._normalize_text(name or "")
        s = re.sub(r"^(project|proj)\s+", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^(مشروع)\s+", "", s)
        s = s.lower()
        s = re.sub(r"[^a-z0-9\u0600-\u06ff\s]+", " ", s)  # keep arabic letters too
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _decode_csv_bytes(file_bytes: bytes) -> Tuple[Optional[List[str]], Optional[str]]:
        encodings_to_try = [
            "utf-8-sig",
            "utf-8",
            "utf-16",
            "utf-16-le",
            "utf-16-be",
            "cp1256",
            "cp1252",
            "latin1",
        ]
        for enc in encodings_to_try:
            try:
                decoded = file_bytes.decode(enc)
                return decoded.splitlines(), None
            except UnicodeDecodeError:
                continue
            except Exception as e:
                return None, str(e)
        return None, "Unsupported file encoding."

    @staticmethod
    def _parse_float(v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        try:
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip().replace(",", "")
            return float(s)
        except Exception:
            return None

    @staticmethod
    def _parse_int(v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            s = str(v).strip()
            if s.isdigit():
                return int(s)
            # allow "00"
            m = re.search(r"(\d+)", s)
            if not m:
                return None
            return int(m.group(1))
        except Exception:
            return None

    @staticmethod
    def _parse_date(v: Any):
        if not v:
            return None
        s = str(v).strip()
        try:
            if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
                y, m, d = s.split("-")
                return timezone.datetime(int(y), int(m), int(d)).date()
            if re.match(r"^\d{2}/\d{2}/\d{4}$", s):
                d, m, y = s.split("/")
                return timezone.datetime(int(y), int(m), int(d)).date()
        except Exception:
            return None
        return None

    @staticmethod
    def _get_project_from_value(value: Any) -> Optional[MarketProject]:
        if value is None or value == "":
            return None
        try:
            pid = int(value)
            return MarketProject.objects.select_related("developer", "location").filter(id=pid).first()
        except Exception:
            pass
        name = MarketResearchUnitsManagmentService._normalize_text(value)
        if not name:
            return None
        # normalized match
        proj = MarketProject.objects.select_related("developer", "location").filter(name__iexact=name).first()
        if proj:
            return proj
        # fallback by normalized key
        key = MarketResearchUnitsManagmentService._project_key(name)
        for p in MarketProject.objects.select_related("developer", "location").all():
            if MarketResearchUnitsManagmentService._project_key(p.name) == key:
                return p
        return None

    @staticmethod
    def _calc_psm(unit_price: Optional[float], bua: Optional[float]) -> Optional[float]:
        if unit_price is None or bua is None or bua == 0:
            return None
        try:
            return float(unit_price) / float(bua)
        except Exception:
            return None

    @staticmethod
    def _calc_months_from_update(date_of_update) -> Optional[int]:
        if not date_of_update:
            return None
        try:
            today = timezone.localdate()
            delta_days = (today - date_of_update).days
            months = round((delta_days / 365.25) * 12)
            months = min(12, max(0, int(months)))
            return months
        except Exception:
            return None

    @staticmethod
    def _parse_payment_raw_to_number(raw: Any) -> float:
        if raw is None or raw == "":
            return 0.0
        s = str(raw).strip()
        m = re.search(r"(\d+(\.\d+)?)", s)
        if not m:
            return 0.0
        try:
            return float(m.group(1))
        except Exception:
            return 0.0

    @staticmethod
    def _format_payment_range(minv: float, maxv: float) -> str:
        left = "Cash" if minv == 0 else f"{int(minv) if float(minv).is_integer() else minv} Yrs"
        if minv == maxv:
            return left
        right = f"{int(maxv) if float(maxv).is_integer() else maxv} Yrs"
        return f"{left} - {right}"

    @staticmethod
    def _recompute_payment_yrs_group(project_name: str, unit_type: str) -> None:
        if not project_name or not unit_type:
            return

        qs = MarketUnitData.objects.filter(project_name__iexact=project_name, unit_type__iexact=unit_type)
        raws = list(qs.values_list("payment_yrs_raw", flat=True))
        nums = [MarketResearchUnitsManagmentService._parse_payment_raw_to_number(r) for r in raws]
        if not nums:
            return

        formatted = MarketResearchUnitsManagmentService._format_payment_range(min(nums), max(nums))
        qs.update(payment_yrs=formatted)

    @staticmethod
    def _get_group_payment_yrs(project_name: str, unit_type: str) -> List[Dict[str, Any]]:
        if not project_name or not unit_type:
            return []
        qs = MarketUnitData.objects.filter(project_name__iexact=project_name, unit_type__iexact=unit_type).values("id", "payment_yrs")
        return [{"id": r["id"], "payment_yrs": r["payment_yrs"]} for r in qs]

    @staticmethod
    def _recompute_row(unit: MarketUnitData, *, compute_psm: bool, compute_months: bool, compute_payment: bool) -> None:
        if compute_psm:
            unit.psm = MarketResearchUnitsManagmentService._calc_psm(unit.unit_price, unit.bua)

        if compute_months:
            unit.months_from_update = MarketResearchUnitsManagmentService._calc_months_from_update(unit.date_of_update)

        if compute_payment and unit.project_name and unit.unit_type:
            MarketResearchUnitsManagmentService._recompute_payment_yrs_group(unit.project_name, unit.unit_type)

    @staticmethod
    def _row_computed_payload(unit: MarketUnitData) -> Dict[str, Any]:
        months = unit.months_from_update
        months_display = str(months).zfill(2) if months is not None else ""
        return {
            "developer_name": unit.developer_name or "",
            "location": unit.location or "",
            "psm": unit.psm if unit.psm is not None else "",
            "payment_yrs": unit.payment_yrs or "",
            "months_from_update_display": months_display,
            "updated_by": unit.updated_by or "",
        }

    # -------- CSV header/key handling --------
    @staticmethod
    def _canon_key(k: str) -> str:
        k = (k or "").strip()
        k = k.replace(".", "")
        k = k.replace("%", " percent ")
        k = k.lower()
        k = re.sub(r"\s+", " ", k).strip()

        k = k.replace("project name", "project_name")
        k = k.replace("developer name", "developer_name")
        k = k.replace("updated by", "updated_by")
        k = k.replace("land area", "land_area")
        k = k.replace("unit price", "unit_price")
        k = k.replace("asset type", "asset_type")
        k = k.replace("unit type", "unit_type")
        k = k.replace("finishing specs", "finishing_specs")
        k = k.replace("source of info", "source_of_info")
        k = k.replace("months from update", "months_from_update")
        k = k.replace("cash discount", "cash_discount")
        k = k.replace("down payment", "down_payment")
        k = k.replace("delivery percent", "delivery_percentage")
        k = k.replace("payment yrs raw", "payment_yrs_raw")
        k = k.replace("payment yrs", "payment_yrs")
        k = k.replace("date of update", "date_of_update")

        k = re.sub(r"[^a-z0-9_]+", "_", k)
        k = re.sub(r"_+", "_", k).strip("_")
        return k

    @staticmethod
    def _canonicalize_row(raw_row: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in (raw_row or {}).items():
            if k is None:
                continue
            ck = MarketResearchUnitsManagmentService._canon_key(str(k))
            if not ck:
                continue
            out[ck] = v
        return out

    @staticmethod
    def _row_looks_like_header(row: Dict[str, Any]) -> bool:
        if not row:
            return True

        def v(name: str) -> str:
            return (row.get(name) or "").strip().lower()

        header_values = {
            "project_name": "project name",
            "developer_name": "developer name",
            "location": "location",
            "asset_type": "asset type",
            "unit_type": "unit type",
            "bua": "bua",
            "unit_price": "unit price",
            "payment_yrs_raw": "payment yrs raw",
            "date_of_update": "date of update",
            "updated_by": "updated by",
            "source_of_info": "source of info",
            "months_from_update": "months from update",
        }

        hits = 0
        for key, expected in header_values.items():
            if v(key) == expected:
                hits += 1

        return hits >= 3 or v("project_name") in ("project name", "project_name")
