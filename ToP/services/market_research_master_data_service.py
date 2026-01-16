# ToP/services/market_research_master_data_service.py

from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type, Tuple, List

from django.db import transaction
from django.db.models import QuerySet

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
    """

    # =========================================================
    # PUBLIC: Context for Master Data Page
    # =========================================================
    @staticmethod
    def get_master_data_context() -> ServiceResult:
        locations = MarketProjectLocation.objects.all()
        developers = MarketProjectDeveloper.objects.all()
        projects = MarketProject.objects.select_related("developer", "location")
        unit_types = MarketUnitType.objects.all()
        finishing_specs = MarketUnitFinishingSpec.objects.all()
        asset_types = MarketUnitAssetType.objects.all()

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

        if model_name == "project":
            # Original logic: value is dict with name/developer_id/location_id
            if not isinstance(value, dict):
                return ServiceResult(success=False, status=400, error="Invalid value for project")

            name = (value.get("name") or "").strip()
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

            # Preserve original response shape
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

        # Simple models: location, developer, unit_type, finishing_spec, asset_type
        model_class = model_map.get(model_name)
        if not model_class:
            return ServiceResult(success=False, status=400, error="Invalid model")

        name = (str(value).strip() if value is not None else "")
        if not name:
            return ServiceResult(success=False, status=400, error="Value is required")

        try:
            obj, _created = model_class.objects.get_or_create(name=name)
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
        # Preserve original validation:
        # if not all([project_id, latitude, longitude]) => error
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
    # PUBLIC: Import CSV For Model
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
                # Original: MarketProjectLocation.objects.update_or_create(name=row['name'].strip())
                for row in reader:
                    name = (row.get("name") or "").strip()
                    if not name:
                        continue
                    MarketProjectLocation.objects.update_or_create(name=name)
                    count += 1

            elif model_name == "developer":
                # Original expects: row['Developer Name']
                for row in reader:
                    name = (row.get("Developer Name") or "").strip()
                    if not name:
                        continue
                    MarketProjectDeveloper.objects.update_or_create(name=name)
                    count += 1

            elif model_name == "unit_type":
                for row in reader:
                    name = (row.get("name") or "").strip()
                    if not name:
                        continue
                    MarketUnitType.objects.update_or_create(name=name)
                    count += 1

            elif model_name == "asset_type":
                for row in reader:
                    name = (row.get("name") or "").strip()
                    if not name:
                        continue
                    MarketUnitAssetType.objects.update_or_create(name=name)
                    count += 1

            elif model_name == "finishing_spec":
                for row in reader:
                    name = (row.get("name") or "").strip()
                    if not name:
                        continue
                    MarketUnitFinishingSpec.objects.update_or_create(name=name)
                    count += 1

            elif model_name == "project":
                # Original expects keys:
                # developer_name = row['Developer Name'], location_name = row['Location'], project_name = row['Project Name ']
                for row in reader:
                    developer_name = (row.get("Developer Name") or "").strip()
                    location_name = (row.get("Location") or "").strip()
                    project_name = (row.get("Project Name ") or "").strip()  # NOTE: trailing space preserved

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
    # INTERNAL: Model map
    # =========================================================
    @staticmethod
    def _model_map(*, include_project: bool = False) -> Dict[str, Type]:
        base = {
            "location": MarketProjectLocation,
            "developer": MarketProjectDeveloper,
            "type": MarketUnitType,
            "finishing_spec": MarketUnitFinishingSpec,
            "asset_type": MarketUnitAssetType,
        }
        if include_project:
            base["project"] = MarketProject
        return base

    # =========================================================
    # INTERNAL: Decode CSV bytes (fallback encodings preserved)
    # =========================================================
    @staticmethod
    def _decode_csv_bytes(file_bytes: bytes) -> Tuple[Optional[List[str]], Optional[str]]:
        # Preserved encodings list and behavior
        encodings_to_try = ["utf-8-sig", "utf-8", "latin1", "cp1252"]

        for enc in encodings_to_try:
            try:
                decoded = file_bytes.decode(enc)
                return decoded.splitlines(), None
            except UnicodeDecodeError:
                continue
            except Exception as e:
                return None, str(e)

        return None, "Unsupported file encoding"
