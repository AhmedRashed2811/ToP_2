import csv
import io
from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
# Added SalesRequest to imports
from ..models import Company, Unit, SalesRequestAnalytical, UnitPosition, UnitPositionChild, SalesRequest

class ImportHubService:
    """
    Service to handle management operations for the Import Hub (Deletions, Renaming, etc).
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

    @staticmethod
    def rename_units_bulk(company_id: int, csv_file) -> dict:
        """
        Renames units based on a CSV file with columns: 'Old Unit Code', 'New Unit Code'.
        Performs a Clone -> Relink -> Delete operation since unit_code is a PK.
        """
        if not company_id:
            raise ValueError("Missing Company ID")

        # Decode CSV file
        decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
        reader = csv.DictReader(decoded_file)
        
        # Normalize headers (strip spaces and lowercase for reliable matching)
        headers = [h.strip().lower() for h in reader.fieldnames or []]
        if 'old unit code' not in headers or 'new unit code' not in headers:
             return {
                "success": False, 
                "error": "CSV must contain 'Old Unit Code' and 'New Unit Code' columns."
            }

        stats = {
            "processed": 0,
            "renamed": 0,
            "skipped_not_found": 0,
            "skipped_duplicate": 0,
            "errors": []
        }

        company = get_object_or_404(Company, id=company_id)

        for row in reader:
            # Flexible key access based on normalized headers
            row_lower = {k.strip().lower(): v.strip() for k, v in row.items()}
            old_code = row_lower.get('old unit code')
            new_code = row_lower.get('new unit code')

            if not old_code or not new_code:
                continue
            
            stats["processed"] += 1

            if old_code == new_code:
                continue

            try:
                with transaction.atomic():
                    # 1. Validation: Check if Old Unit exists in this company
                    try:
                        old_unit = Unit.objects.get(unit_code=old_code, company=company)
                    except Unit.DoesNotExist:
                        stats["skipped_not_found"] += 1
                        stats["errors"].append(f"Row {stats['processed']}: Old unit '{old_code}' not found in this warehouse.")
                        continue

                    # 2. Validation: Check if New Unit Code already exists (Global check to prevent PK collision)
                    if Unit.objects.filter(unit_code=new_code).exists():
                        stats["skipped_duplicate"] += 1
                        stats["errors"].append(f"Row {stats['processed']}: New unit code '{new_code}' already exists.")
                        continue

                    # 3. CLONE: Create new unit with old data
                    # We iterate over fields to copy values, skipping the PK
                    new_unit = Unit(unit_code=new_code)
                    for field in Unit._meta.fields:
                        if field.name != 'unit_code':
                            setattr(new_unit, field.name, getattr(old_unit, field.name))
                    
                    new_unit.save()

                    # 4. RELINK: Update references in related models
                    
                    # A. Update Text-Based References (Loose Coupling)
                    SalesRequestAnalytical.objects.filter(unit_code=old_code).update(unit_code=new_code)
                    UnitPosition.objects.filter(unit_code=old_code).update(unit_code=new_code)
                    UnitPositionChild.objects.filter(unit_code=old_code).update(unit_code=new_code)

                    # B. Update ForeignKey References (Strict Coupling - SalesRequest)
                    # We MUST do this before deleting old_unit, or the link becomes NULL
                    SalesRequest.objects.filter(unit=old_unit).update(unit=new_unit)

                    # 5. DELETE: Remove the old unit
                    old_unit.delete()

                    stats["renamed"] += 1

            except Exception as e:
                stats["errors"].append(f"Error renaming '{old_code}' to '{new_code}': {str(e)}")

        return {"success": True, "stats": stats}