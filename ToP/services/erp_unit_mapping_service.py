import json
from dataclasses import dataclass
from typing import Dict, List

from django.db import transaction
from ..models import Company, Unit, ERPUnitFieldMapping


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: dict = None
    error: str = ""


class ERPUnitMappingService:

    @staticmethod
    def get_unit_field_names() -> List[str]:
        """
        Returns valid Unit model field names for validation/autocomplete.
        """
        return [
            f.name for f in Unit._meta.get_fields()
            if hasattr(f, "attname") and getattr(f, "concrete", False)
        ]

    @staticmethod
    def get_mapping_dict(*, company: Company) -> Dict[str, str]:
        """
        Returns: {provided_name: needed_name}
        """
        qs = ERPUnitFieldMapping.objects.filter(company=company, is_active=True)
        return {m.provided_name.strip(): m.needed_name.strip() for m in qs}

    @staticmethod
    @transaction.atomic
    def save_mappings(*, company: Company, mappings: List[dict]) -> ServiceResult:
        """
        mappings = [{"provided_name":"price", "needed_name":"interest_free_unit_price"}, ...]
        - Upsert provided_name rows
        - Disable missing rows
        """
        allowed_fields = set(ERPUnitMappingService.get_unit_field_names())

        clean_incoming = []
        for row in mappings:
            p = (row.get("provided_name") or "").strip()
            n = (row.get("needed_name") or "").strip()
            if not p or not n:
                continue
            if n not in allowed_fields:
                return ServiceResult(
                    success=False,
                    status=400,
                    payload={"success": False, "error": f"Invalid needed name: '{n}' (not a Unit field)"},
                    error="invalid_needed_name"
                )
            clean_incoming.append((p, n))

        # Disable all existing first (then re-enable only what is sent)
        ERPUnitFieldMapping.objects.filter(company=company).update(is_active=False)

        # Upsert
        for provided_name, needed_name in clean_incoming:
            obj, _created = ERPUnitFieldMapping.objects.update_or_create(
                company=company,
                provided_name=provided_name,
                defaults={"needed_name": needed_name, "is_active": True}
            )

        return ServiceResult(
            success=True,
            status=200,
            payload={"success": True, "count": len(clean_incoming)}
        )

