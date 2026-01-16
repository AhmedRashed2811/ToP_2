from django.shortcuts import get_object_or_404
from ..models import Company, Unit

class ImportHubService:
    """
    Service to handle management operations for the Import Hub (Deletions, etc).
    """

    @staticmethod
    def delete_units_bulk(company_id: int, unit_codes: list) -> dict:
        """
        Deletes units for a specific company based on a list of unit codes.
        """
        if not company_id:
            raise ValueError("Missing Company ID")
        
        if not unit_codes:
            return {"success": True, "deleted_count": 0, "not_found_count": 0}

        company = get_object_or_404(Company, id=company_id)

        # Filter units belonging to this company with provided codes
        units_to_delete = Unit.objects.filter(
            company=company,
            unit_code__in=unit_codes
        )
        
        count = units_to_delete.count()
        not_found = len(unit_codes) - count
        
        # Execute Delete
        units_to_delete.delete()

        return {
            "success": True,
            "deleted_count": count,
            "not_found_count": not_found
        }