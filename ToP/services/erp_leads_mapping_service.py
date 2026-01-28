from dataclasses import dataclass
from typing import Dict, List
from django.db import transaction

from ..models import Company, ERPLeadsFieldMapping


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: dict = None
    error: str = ""


class ERPLeadsMappingService:
    """
    Separate mapping for Leads API.

    Note: Unlike Unit mapping, Leads targets may differ between companies.
    So we keep it flexible (no strict validation on needed_name).
    """

    @staticmethod
    def get_mapping_dict(*, company: Company) -> Dict[str, str]:
        qs = ERPLeadsFieldMapping.objects.filter(company=company, is_active=True)
        return {m.provided_name.strip(): m.needed_name.strip() for m in qs}

    @staticmethod
    def get_common_leads_keys() -> List[str]:
        """
        Optional suggestions for UI datalist (not enforced).
        Adjust to your own CRM schema if you have one.
        """
        return [
            "lead_id", "id", "name", "full_name",
            "phone", "mobile", "email",
            "source", "stage", "status",
            "created_at", "created_on", "created_date",
            "assigned_to", "owner", "sales_person",
            "notes", "comment", "message",
        ]

    @staticmethod
    @transaction.atomic
    def save_mappings(*, company: Company, mappings: List[dict]) -> ServiceResult:
        """
        mappings = [{"provided_name":"clientMobile", "needed_name":"phone"}, ...]
        - Disable all then upsert incoming
        """
        clean_incoming = []
        for row in mappings:
            p = (row.get("provided_name") or "").strip()
            n = (row.get("needed_name") or "").strip()
            if not p or not n:
                continue
            clean_incoming.append((p, n))

        ERPLeadsFieldMapping.objects.filter(company=company).update(is_active=False)

        for provided_name, needed_name in clean_incoming:
            ERPLeadsFieldMapping.objects.update_or_create(
                company=company,
                provided_name=provided_name,
                defaults={"needed_name": needed_name, "is_active": True}
            )

        return ServiceResult(
            success=True,
            status=200,
            payload={"success": True, "count": len(clean_incoming)}
        )
