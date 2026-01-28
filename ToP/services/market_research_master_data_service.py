# ToP/services/market_research_master_data_service.py
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type, Tuple, List

from django.db import transaction

from ..models import (
    MarketProjectLocation,
    MarketProjectDeveloper,
    MarketProject,
    MarketUnitType,
    MarketUnitFinishingSpec,
    MarketUnitAssetType,
)


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MarketResearchMasterDataService:
    """
    Service layer for Market Research Master Data.
    - Views must not use utils.
    - Service does not accept HttpRequest.
    - Preserves original logic (critical).
    - Adds robust Unicode normalization for Arabic/non-English inputs (create + CSV import).
    """

    # =========================================================
    # PUBLIC: Context for Master Data Page
    # =========================================================
    @staticmethod
    def get_master_data_context() -> ServiceResult:
        locations = MarketProjectLocation.objects.all().order_by("name")
        developers = MarketProjectDeveloper.objects.all().order_by("name")
        projects = MarketProject.objects.select_related("developer", "location").order_by("name")
        unit_types = MarketUnitType.objects.all().order_by("name")
        finishing_specs = MarketUnitFinishingSpec.objects.all().order_by("name")
        asset_types = MarketUnitAssetType.objects.all().order_by("name")

        return ServiceResult(
            success=True,
            status=200,
            payload={
                "locations": locations,
                "developers": developers,
                "projects": projects,
                "unit_types": unit_types,
                "finishing_specs": finishing_specs,
                "asset_types": asset_types,
            },
        )

    # =========================================================
    # PUBLIC: Create Entry
    # =========================================================
    @staticmethod
    @transaction.atomic
    def create_entry(*, model_name: Optional[str], value: Any) -> ServiceResult:
        model_map = MarketResearchMasterDataService._model_map()

        if not model_name:
            return ServiceResult(success=False, status=400, error="Model name not provided")

        # ---- Project (preserve original shape, but normalize name) ----
        if model_name == "project":
            if not isinstance(value, dict):
                return ServiceResult(success=False, status=400, error="Invalid value for project")

            name = MarketResearchMasterDataService._normalize_name(value.get("name"))
            developer_id = value.get("developer_id")
            location_id = value.get("location_id")

            if not name or not developer_id or not location_id:
                return ServiceResult(success=False, status=400, error="Missing required project fields")

            try:
                project = MarketProject.objects.create(
                    name=name,
                    developer_id=developer_id,
                    location_id=location_id,
                )
            except Exception as e:
                return ServiceResult(success=False, status=400, error=str(e))

            return ServiceResult(
                success=True,
                status=200,
                payload={
                    "id": project.id,
                    "name": project.name,
                    "developer": project.developer.name,
                    "location": project.location.name,
                },
            )

        # ---- Simple master tables ----
        model_class = model_map.get(model_name)
        if not model_class:
            return ServiceResult(success=False, status=400, error="Invalid model")

        name = MarketResearchMasterDataService._normalize_name(value)
        if not name:
            return ServiceResult(success=False, status=400, error="Value is required")

        try:
            # Prevent duplicates caused by different case/spacing/Unicode forms
            existing = model_class.objects.filter(name__iexact=name).first()
            if existing:
                return ServiceResult(success=True, status=200, payload={"id": existing.id, "name": existing.name})

            obj = model_class.objects.create(name=name)
            return ServiceResult(success=True, status=200, payload={"id": obj.id, "name": obj.name})
        except Exception as e:
            return ServiceResult(success=False, status=400, error=str(e))

    # =========================================================
    # PUBLIC: Delete Entry
    # =========================================================
    @staticmethod
    @transaction.atomic
    def delete_entry(*, model_name: Optional[str], obj_id: Any) -> ServiceResult:
        model_map = MarketResearchMasterDataService._model_map(include_project=True)

        if not model_name:
            return ServiceResult(success=False, status=400, error="Model name not provided")

        model_class = model_map.get(model_name)
        if not model_class:
            return ServiceResult(success=False, status=400, error="Invalid model")

        try:
            instance = model_class.objects.get(pk=obj_id)
        except model_class.DoesNotExist:
            return ServiceResult(success=False, status=404, error="Not found")
        except Exception as e:
            return ServiceResult(success=False, status=400, error=str(e))

        try:
            instance.delete()
            return ServiceResult(success=True, status=200, payload={"success": True})
        except Exception as e:
            return ServiceResult(success=False, status=400, error=str(e))

    # =========================================================
    # PUBLIC: Save Project Location (lat/lng)
    # =========================================================
    @staticmethod
    @transaction.atomic
    def save_project_location(*, project_id: Any, latitude: Any, longitude: Any) -> ServiceResult:
        # Preserve original validation behavior
        if not project_id or latitude is None or longitude is None:
            return ServiceResult(success=False, status=400, error="Missing required fields")

        try:
            project = MarketProject.objects.get(pk=project_id)
        except MarketProject.DoesNotExist:
            return ServiceResult(success=False, status=404, error="Project not found")
        except Exception as e:
            return ServiceResult(success=False, status=400, error=str(e))

        try:
            project.latitude = latitude
            project.longitude = longitude
            project.save()
            return ServiceResult(success=True, status=200, payload={"success": True})
        except Exception as e:
            return ServiceResult(success=False, status=400, error=str(e))

    # =========================================================
    # PUBLIC: Import CSV For Model (Arabic-safe decoding + normalization)
    # =========================================================
    @staticmethod
    @transaction.atomic
    def import_csv_for_model(*, model_name: Optional[str], file_bytes: bytes) -> ServiceResult:
        if not model_name:
            return ServiceResult(success=False, status=400, error="Model name not provided")

        if not file_bytes:
            return ServiceResult(success=False, status=400, error="Empty file")

        decoded_lines, decode_err = MarketResearchMasterDataService._decode_csv_bytes(file_bytes)
        if decoded_lines is None:
            return ServiceResult(success=False, status=400, error=decode_err or "Unsupported file encoding")

        try:
            reader = csv.DictReader(decoded_lines)
        except Exception as e:
            return ServiceResult(success=False, status=400, error=str(e))

        count = 0

        try:
            if model_name == "location":
                for row in reader:
                    name = MarketResearchMasterDataService._normalize_name(row.get("name"))
                    if not name:
                        continue
                    MarketProjectLocation.objects.update_or_create(name=name)
                    count += 1

            elif model_name == "developer":
                for row in reader:
                    name = MarketResearchMasterDataService._normalize_name(
                        row.get("Developer Name") or row.get("developer") or row.get("name")
                    )
                    if not name:
                        continue
                    MarketProjectDeveloper.objects.update_or_create(name=name)
                    count += 1

            elif model_name in ("unit_type", "type"):
                for row in reader:
                    name = MarketResearchMasterDataService._normalize_name(row.get("name"))
                    if not name:
                        continue
                    MarketUnitType.objects.update_or_create(name=name)
                    count += 1

            elif model_name == "asset_type":
                for row in reader:
                    name = MarketResearchMasterDataService._normalize_name(row.get("name"))
                    if not name:
                        continue
                    MarketUnitAssetType.objects.update_or_create(name=name)
                    count += 1

            elif model_name == "finishing_spec":
                for row in reader:
                    name = MarketResearchMasterDataService._normalize_name(row.get("name"))
                    if not name:
                        continue
                    MarketUnitFinishingSpec.objects.update_or_create(name=name)
                    count += 1

            elif model_name == "project":
                for row in reader:
                    developer_name = MarketResearchMasterDataService._normalize_name(
                        row.get("Developer Name") or row.get("Developer") or row.get("developer")
                    )
                    location_name = MarketResearchMasterDataService._normalize_name(
                        row.get("Location") or row.get("location")
                    )
                    project_name = MarketResearchMasterDataService._normalize_name(
                        row.get("Project Name ") or row.get("Project Name") or row.get("project")
                    )  # preserve trailing-space-key compatibility

                    if not developer_name or not location_name or not project_name:
                        continue

                    developer, _ = MarketProjectDeveloper.objects.get_or_create(name=developer_name)
                    location, _ = MarketProjectLocation.objects.get_or_create(name=location_name)

                    MarketProject.objects.update_or_create(
                        name=project_name,
                        defaults={"developer": developer, "location": location},
                    )
                    count += 1

            else:
                return ServiceResult(success=False, status=400, error="Invalid model")

            return ServiceResult(success=True, status=200, payload={"success": True, "count": count})

        except Exception as e:
            return ServiceResult(success=False, status=400, error=str(e))

    # =========================================================
    # INTERNAL: Model map (adds aliases to avoid breaking old keys)
    # =========================================================
    @staticmethod
    def _model_map(*, include_project: bool = False) -> Dict[str, Type]:
        base: Dict[str, Type] = {
            "location": MarketProjectLocation,
            "developer": MarketProjectDeveloper,
            # Unit type aliases (your template/service had inconsistent keys before)
            "type": MarketUnitType,
            "unit_type": MarketUnitType,
            "finishing_spec": MarketUnitFinishingSpec,
            "asset_type": MarketUnitAssetType,
        }
        if include_project:
            base["project"] = MarketProject
        return base

    # =========================================================
    # INTERNAL: Unicode normalize (Arabic-safe)
    # =========================================================
    @staticmethod
    def _normalize_name(raw: Any) -> str:
        if raw is None:
            return ""

        s = str(raw)

        # Remove BOM / zero-widths sometimes found in Arabic CSV exports
        s = s.replace("\ufeff", "").replace("\u200f", "").replace("\u200e", "")

        # Normalize Unicode (handles Arabic presentation forms, full-width chars, etc.)
        s = unicodedata.normalize("NFKC", s)

        # Remove Arabic tatweel + common diacritics (tashkeel) so duplicates don't happen
        # tatweel: \u0640
        # harakat: \u064b-\u065f, \u0670
        s = re.sub(r"[\u0640\u064b-\u065f\u0670]", "", s)

        # Collapse whitespace
        s = re.sub(r"\s+", " ", s, flags=re.UNICODE).strip()

        return s

    # =========================================================
    # INTERNAL: Decode CSV bytes (adds Arabic encodings)
    # =========================================================
    @staticmethod
    def _decode_csv_bytes(file_bytes: bytes):
        encodings_to_try = [
            "utf-8-sig",
            "utf-8",
            "utf-16",
            "utf-16-le",
            "utf-16-be",
            "cp1256",   # Arabic Windows Excel ANSI
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

        return None, "Unsupported file encoding"
    
    
    
