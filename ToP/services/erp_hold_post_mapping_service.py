from dataclasses import dataclass
from typing import Dict, List
from django.db import transaction

from ..models import Company, ERPHoldPostFieldMapping


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: dict = None
    error: str = ""


class ERPHoldPostMappingService:
    """
    Separate mapping for HOLD/BLOCK POST payload keys.
    IMPORTANT:
      We store mapping in the same UI direction as other mappings:
        provided_name (ERP key) -> needed_name (our internal key)

      When building outgoing payload, we INVERT this mapping.
    """

    @staticmethod
    def get_mapping_dict(*, company: Company) -> Dict[str, str]:
        qs = ERPHoldPostFieldMapping.objects.filter(company=company, is_active=True)
        # ERP expected key -> our internal key
        return {m.provided_name.strip(): m.needed_name.strip() for m in qs}

    @staticmethod
    def get_common_hold_post_keys() -> List[str]:
        """
        Suggestions for the 'Needed Name' column (our internal keys).
        Not enforced, just for datalist help.
        """
        return [
            "unit_code",
            "type",
            "status",
            "status_reason",
            "reason",
            "action",
            "note",
            "comment",
        ]

    @staticmethod
    @transaction.atomic
    def save_mappings(*, company: Company, mappings: List[dict]) -> ServiceResult:
        """
        mappings = [{"provided_name":"ced_name", "needed_name":"unit_code"}, ...]
        Strategy:
          - disable all existing
          - upsert incoming as active
        """
        clean_incoming = []
        for row in mappings:
            p = (row.get("provided_name") or "").strip()
            n = (row.get("needed_name") or "").strip()
            if not p or not n:
                continue
            clean_incoming.append((p, n))

        ERPHoldPostFieldMapping.objects.filter(company=company).update(is_active=False)

        for provided_name, needed_name in clean_incoming:
            ERPHoldPostFieldMapping.objects.update_or_create(
                company=company,
                provided_name=provided_name,
                defaults={"needed_name": needed_name, "is_active": True}
            )

        return ServiceResult(
            success=True,
            status=200,
            payload={"success": True, "count": len(clean_incoming)}
        )
