import logging
import traceback
import json
from typing import List, Dict, Any
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from ..models import Unit, Company, Project
from ..utils.csv_inventory_utils import read_csv_rows, normalize_row, convert_date_format
from .erp_import_service import ERPImportService

# Google Sheets imports (lazy load in method usually better, but here for structure)
try:
    from ..utils.google_sheets_utils import gspread_client, resolve_worksheet
except ImportError:
    gspread_client = None

logger = logging.getLogger(__name__)

class UnitWarehouseService:
    """
    Central engine for Unit Warehouse.
    1. Fetches data from source (ERP, Sheet, CSV).
    2. Merges data into Unit model (Upsert).
    """

    @staticmethod
    def trigger_import(company: Company, source_type: str, file_data=None) -> Dict[str, Any]:
        """
        Orchestrator: Fetches data based on source_type, then calls merge_inventory.
        """
        units_payload = []
        
        try:
            # 1. FETCH DATA
            if source_type == "erp":
                units_payload = ERPImportService.fetch_units(company)
            
            elif source_type == "sheet":
                units_payload = UnitWarehouseService._fetch_from_sheet(company)
            
            elif source_type == "csv":
                if not file_data:
                    raise ValueError("No CSV file provided.")
                units_payload = UnitWarehouseService._fetch_from_csv(file_data)
            
            else:
                raise ValueError(f"Unknown source type: {source_type}")

            # 2. MERGE DATA
            return UnitWarehouseService.merge_inventory(
                company=company,
                source_label=source_type.upper(),
                units_data=units_payload
            )

        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    # --- Fetch Helpers ---

    @staticmethod
    def _fetch_from_sheet(company: Company) -> List[Dict]:
        if not company.google_sheet_url:
            raise ValueError("Google Sheet URL not configured for this company.")
        
        if not gspread_client:
            raise ImportError("Google Sheets libraries not installed or utils missing.")

        gc = gspread_client(company)
        sh = gc.open_by_url(company.google_sheet_url)
        ws = resolve_worksheet(sh, company.google_sheet_gid, company.google_sheet_title)
        
        raw_rows = ws.get_all_records()
        payload = []

        for row in raw_rows:
            # Normalize keys to lowercase/snake_case
            clean_row = {str(k).strip().lower().replace(" ", "_"): v for k, v in row.items()}
            
            # Identify Unit Code
            # Check normalized keys or fallback to common variations
            u_code = (
                clean_row.get("unit_code") or 
                row.get("Unit Code") or 
                row.get("UnitCode") or 
                row.get("Code")
            )
            
            if u_code:
                clean_row['unit_code'] = str(u_code)
                payload.append(clean_row)
        
        return payload

    @staticmethod
    def _fetch_from_csv(file_obj) -> List[Dict]:
        # Save temp file
        path = default_storage.save(f"temp/{file_obj.name}", ContentFile(file_obj.read()))
        payload = []
        
        try:
            raw_rows = read_csv_rows(path)
            for row in raw_rows:
                norm_row = normalize_row(row) # utility that normalizes keys
                u_code = norm_row.get("Unit Code") # normalize_row usually standardizes to Title Case keys
                
                if u_code:
                    # Convert to model-friendly snake_case
                    mapped = {
                        str(k).strip().lower().replace(" ", "_"): v 
                        for k, v in norm_row.items()
                    }
                    mapped['unit_code'] = u_code
                    payload.append(mapped)
        finally:
            if default_storage.exists(path):
                default_storage.delete(path)
        
        return payload

    # --- Merge Logic ---

    @staticmethod
    def merge_inventory(company: Company, source_label: str, units_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upserts units into the database.
        """
        stats = {
            "total_received": len(units_data),
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": []
        }

        existing_units_map = {
            u.unit_code: u 
            for u in Unit.objects.filter(company=company)
        }

        units_to_create = []
        units_to_update = []
        
        for index, row_data in enumerate(units_data):
            try:
                unit_code = str(row_data.get("unit_code", "")).strip()
                if not unit_code:
                    stats["skipped"] += 1
                    continue

                clean_data = UnitWarehouseService._clean_row_data(row_data)
                clean_data['company'] = company
                # clean_data['source'] = source_label # Uncomment if you have a 'source' field on Unit

                # Resolve Project Link
                if 'project' in clean_data and isinstance(clean_data['project'], str):
                    proj_name = clean_data['project']
                    project_obj = Project.objects.filter(name__iexact=proj_name).first()
                    # Fallback: check if project belongs to this company specifically if needed
                    if project_obj:
                        clean_data['project_company'] = project_obj

                if unit_code in existing_units_map:
                    # UPDATE
                    existing_unit = existing_units_map[unit_code]
                    has_changes = False
                    
                    for field, new_value in clean_data.items():
                        if field == 'unit_code': continue
                        
                        if new_value is not None: 
                            current_val = getattr(existing_unit, field, None)
                            if str(current_val) != str(new_value): # String comparison for safety
                                setattr(existing_unit, field, new_value)
                                has_changes = True
                    
                    if has_changes:
                        units_to_update.append(existing_unit)
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    # CREATE
                    if 'unit_code' in clean_data: del clean_data['unit_code']
                    new_unit = Unit(unit_code=unit_code, **clean_data)
                    units_to_create.append(new_unit)
                    stats["created"] += 1

            except Exception as e:
                stats["errors"].append(f"Row {index}: {str(e)}")

        # Batch Operations
        SAFE_BATCH_SIZE = 50 
        try:
            with transaction.atomic():
                if units_to_create:
                    Unit.objects.bulk_create(units_to_create, batch_size=SAFE_BATCH_SIZE)
                
                if units_to_update:
                    # Get fields to update (exclude PK/unique)
                    update_fields = [f.name for f in Unit._meta.fields if f.name not in ['id', 'unit_code', 'company']]
                    # Filter update_fields to only those present in our clean data logic if strictly necessary, 
                    # but bulk_update requires a fixed list. Using all mutable fields is standard.
                    Unit.objects.bulk_update(units_to_update, fields=update_fields, batch_size=SAFE_BATCH_SIZE)
                    
        except Exception as e:
            return {"success": False, "error": f"Database Commit Failed: {str(e)}", "stats": stats}

        return {"success": True, "message": "Import completed successfully", "stats": stats}

    @staticmethod
    def _clean_row_data(row_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cleans row data against Unit model fields.
        """
        clean = {}
        model_fields = {f.name: f for f in Unit._meta.get_fields()}

        for k, v in row_data.items():
            if k in model_fields:
                field = model_fields[k]
                
                # Auto-convert dates
                if field.get_internal_type() == 'DateField' and v:
                    v = convert_date_format(str(v))

                # Handle Empty Strings for nullable fields
                if v == "" and k not in ['unit_code', 'project', 'city']: 
                    clean[k] = None
                else:
                    clean[k] = v
                    
        return clean