# ToP/services/csv_inventory_service.py

import uuid
import threading

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from ..models import Company, Unit, Project, ModificationRecords
from ..utils.csv_inventory_utils import (
    progress_get,
    progress_set_processing,
    progress_set_completed,
    progress_set_error,
    validate_csv_file_or_response,
    read_csv_rows,
    normalize_row,
    clean_numeric, 
    convert_date_format
)

class CsvInventoryService:
    """
    Unified CSV Inventory feature service:
    - start_upload()   -> validate + save temp + spawn thread
    - run_import()     -> read csv + replace/update + upsert units + progress
    - get_progress()   -> read cache progress

    Behavior is preserved exactly.
    """

    # =========================
    # PUBLIC API (Views use only these)
    # =========================

    @staticmethod
    def get_progress(task_id: str):
        return progress_get(task_id)

    @classmethod
    def start_upload(cls, *, user, files, data):
        """
        Equivalent to old CsvUploadService.start_upload.
        Returns JsonResponse or None.
        """

        # 1) Validate file (same behavior)
        csv_file = files.get("csv_file")
        invalid_response = validate_csv_file_or_response(csv_file)
        if invalid_response:
            return invalid_response

        # 2) Validate company (same behavior)
        company_id = data.get("company_id")
        if not company_id:
            return JsonResponse(
                {"error": "You must select a company to link the units to."},
                status=400,
            )
        company = get_object_or_404(Company, id=company_id)

        # 3) Save temp file (same behavior)
        file_path = default_storage.save(
            f"temp_uploads/{uuid.uuid4()}_{csv_file.name}",
            ContentFile(csv_file.read()),
        )

        # 4) Determine upload mode (same behavior)
        upload_mode = data.get("upload_mode", "insert_new")
        is_replace_mode = False

        if upload_mode == "replace_all":
            if user.groups.filter(name__in=["TeamMember", "Admin", "Developer"]).exists():
                is_replace_mode = True
            else:
                return JsonResponse({"error": "Permission Denied for Replace All"}, status=403)

        # 5) Start background thread (same behavior)
        task_id = str(uuid.uuid4())

        thread = threading.Thread(
            target=cls.run_import,
            kwargs={
                "task_id": task_id,
                "file_path": file_path,
                "company_id": company.id,
                "user_id": user.id,
                "upload_mode": upload_mode,
                "is_replace_mode": is_replace_mode,
            },
        )
        thread.daemon = True
        thread.start()

        return JsonResponse({"task_id": task_id, "status": "started"})

    @classmethod
    def run_import(cls, *, task_id: str, file_path: str, company_id: int, user_id: int, upload_mode: str, is_replace_mode: bool):
        """
        Equivalent to old CsvInventoryImportService.run.
        """
        try:
            user, company = cls._load_user_and_company(user_id, company_id)
            rows = read_csv_rows(file_path)  # utf-8-sig + DictReader
            total_rows = len(rows)

            cls._handle_replace_mode(company=company, user=user, is_replace_mode=is_replace_mode)

            cls._process_rows(
                task_id=task_id,
                rows=rows,
                total_rows=total_rows,
                company=company,
            )

            progress_set_completed(task_id)

        except Exception as e:
            progress_set_error(task_id, str(e))

        finally:
            # Same behavior: always delete temp file
            if default_storage.exists(file_path):
                default_storage.delete(file_path)

    # =========================
    # INTERNALS
    # =========================

    @staticmethod
    def _load_user_and_company(user_id: int, company_id: int):
        User = get_user_model()
        user = User.objects.get(id=user_id)
        company = Company.objects.get(id=company_id)
        return user, company

    @staticmethod
    def _handle_replace_mode(*, company, user, is_replace_mode: bool):
        if is_replace_mode:
            Unit.objects.filter(company=company).delete()
            ModificationRecords.objects.create(
                user=user,
                type="REPLACE",
                description=f"Replaced All {company.name} Units with New Inventory.",
            )
        else:
            ModificationRecords.objects.create(
                user=user,
                type="UPDATE",
                description=f"Updated {company.name} Units with New Inventory.",
            )

    @classmethod
    def _process_rows(cls, *, task_id: str, rows, total_rows: int, company):
        last_project_name = None
        proj_obj = None

        for index, row in enumerate(rows):
            # Same logic: update progress every 10 rows or last row
            progress_set_processing(task_id, index=index, total_rows=total_rows)

            row = normalize_row(row)

            unit_code = row.get("Unit Code", "").strip()
            if not unit_code:
                continue

            current_project_name = row.get("Project", "").strip()

            if current_project_name != last_project_name:
                proj_obj = (
                    Project.objects.filter(name__iexact=current_project_name).first()
                    if current_project_name
                    else None
                )
                last_project_name = current_project_name

            cls._upsert_unit(
                company=company,
                unit_code=unit_code,
                row=row,
                project_name=current_project_name,
                proj_obj=proj_obj,
            )

    @staticmethod
    def _upsert_unit(*, company, unit_code: str, row, project_name: str, proj_obj):
        """
        IMPORTANT: defaults dict is kept IDENTICAL to your original implementation.
        """
        Unit.objects.update_or_create(
            unit_code=unit_code,
            company=company,
            defaults={
                'city': row.get('City', None),
                'project': project_name,
                'project_company': proj_obj,

                'sales_phasing': row.get('Sales Phasing', None),
                'construction_phasing': row.get('Construction Phasing', None),
                'handover_phasing': row.get('Handover Phasing', None),
                'plot_type': row.get('Plot Type', None),
                'building_style': row.get('Building Style', None),
                'building_type': row.get('Building Type', None),
                'unit_type': row.get('Unit Type', None),
                'unit_model': row.get('Unit Model', None),
                'mirror': row.get('Mirror', None),
                'unit_position': row.get('Unit Position', None),
                'building_number': row.get('Building Number', None),
                'floor': row.get('Floor', None),
                'sap_code': row.get('SAP Code', None),

                'finishing_specs': row.get('Finishing Specs', None),
                'num_bedrooms': row.get('Num Bedrooms', '0'),
                'num_bathrooms': row.get('Num Bathrooms', '0'),
                'num_parking_slots': clean_numeric(row.get('Num Parking Slots', '0')),

                'footprint': float(row.get('Foot print', 0)) if row.get('Foot print') else None,
                'internal_area': float(row.get('Internal Area', 0)) if row.get('Internal Area') else None,
                'covered_terraces': float(row.get('Covered Terraces', 0)) if row.get('Covered Terraces') else None,
                'uncovered_terraces': float(row.get('Uncovered Terraces', 0)) if row.get('Uncovered Terraces') else None,
                'penthouse_area': float(row.get('Penthouse Area', 0)) if row.get('Penthouse Area') else None,
                'garage_area': float(row.get('Garage Area', 0)) if row.get('Garage Area') else None,
                'basement_area': float(row.get('Basement Area', 0)) if row.get('Basement Area') else None,
                'net_area': float(row.get('Net Area', 0)) if row.get('Net Area') else None,
                'common_area': float(row.get('Common Area', 0)) if row.get('Common Area') else None,
                'gross_area': float(row.get('Gross Area', 0)) if row.get('Gross Area') else None,
                'roof_pergola_area': float(row.get('Roof Pergola Area', 0)) if row.get('Roof Pergola Area') else None,
                'roof_terraces_area': float(row.get('Roof Terraces Area', 0)) if row.get('Roof Terraces Area') else None,
                'bua': float(row.get('BUA', 0)) if row.get('BUA') else None,
                'land_area': float(row.get('Land Area', 0)) if row.get('Land Area') else None,
                'garden_area': float(row.get('Garden Area', 0)) if row.get('Garden Area') else None,
                'total_area': float(row.get('Total Area', 0)) if row.get('Total Area') else None,

                'net_area_psm': float(row.get('Net Area PSM', 0)) if row.get('Net Area PSM') else None,
                'covered_terraces_psm': float(row.get('Covered Terraces PSM', 0)) if row.get('Covered Terraces PSM') else None,
                'uncovered_terraces_psm': float(row.get('Uncovered Terraces PSM', 0)) if row.get('Uncovered Terraces PSM') else None,
                'penthouse_psm': float(row.get('Penthouse PSM', 0)) if row.get('Penthouse PSM') else None,
                'garage_psm': float(row.get('Garage PSM', 0)) if row.get('Garage PSM') else None,
                'basement_psm': float(row.get('Basement PSM', 0)) if row.get('Basement PSM') else None,
                'common_area_psm': float(row.get('Common Area PSM', 0)) if row.get('Common Area PSM') else None,
                'roof_pergola_psm': float(row.get('Roof Pergola PSM', 0)) if row.get('Roof Pergola PSM') else None,
                'roof_terraces_psm': float(row.get('Roof Terraces PSM', 0)) if row.get('Roof Terraces PSM') else None,
                'land_psm': float(row.get('Land PSM', 0)) if row.get('Land PSM') else None,
                'garden_psm': float(row.get('Garden PSM', 0)) if row.get('Garden PSM') else None,

                'base_price': float(row.get('Unit Base Price', 0)) if row.get('Unit Base Price') else None,
                'base_psm': float(row.get('Base PSM', 0)) if row.get('Base PSM') else None,

                'main_view': row.get('Main View', None),
                'secondary_view': row.get('Secondary View', None),
                'levels': row.get('Levels', None),
                'north_breeze': row.get('North Breeze', None),
                'corners': row.get('Corners', None),
                'accessibility': row.get('Accessibility', None),
                'special_premiums': row.get('Special Premiums & Discounts', None),
                'special_discounts': row.get('Special Premiums & Discounts', None),

                'total_premium_percent': float(row.get('Total Premium Percent', 0))
                    if row.get('Total Premium Percent') else None,
                'total_premium_value': float(row.get('Total Premium Value', 0))
                    if row.get('Total Premium Value') else None,

                'interest_free_unit_price': float(row.get('Interest Free Unit Price', 0))
                    if row.get('Interest Free Unit Price') else None,
                'interest_free_psm': float(row.get('Interest Free PSM', 0))
                    if row.get('Interest Free PSM') else None,
                'interest_free_years': clean_numeric(row.get('Interest Free Years', '0')),

                'down_payment_percent': float(row.get('Down Payment Percent', 0))
                    if row.get('Down Payment %') else None,
                'down_payment': float(row.get('Down Payment', 0))
                    if row.get('Down Payment') else None,
                'contract_percent': float(row.get('Contract Percent', 0))
                    if row.get('Contract %') else None,
                'contract_payment': float(row.get('Contract Payment', 0))
                    if row.get('Contract Payment') else None,
                'delivery_percent': float(row.get('Delivery Percent', 0))
                    if row.get('Delivery %') else None,
                'delivery_payment': float(row.get('Delivery Payment', 0))
                    if row.get('Delivery Payment') else None,
                'cash_price': float(row.get('Cash Price', 0))
                    if row.get('Cash Price') else None,

                'maintenance_percent': float(row.get('Maintenance Percent', 0))
                    if row.get('Maintenance Percent') else None,
                'maintenance_value': float(row.get('Maintenance Value', 0))
                    if row.get('Maintenance Value') else None,

                'club': row.get('Club', None),
                'gas': float(row.get('Gas', 0)) if row.get('Gas') else None,
                'parking_price': float(row.get('Parking Price', 0))
                    if row.get('Parking Price') else None,

                'status': row.get('Status', None),
                'owner': row.get('Owner', None),
                'blocking_reason': row.get('Blocking Reason', None),

                'release_date': convert_date_format(row.get('Release Date')),
                'blocking_date': convert_date_format(row.get('Blocking Date')),
                'reservation_date': convert_date_format(row.get('Reservation Date')),
                'contract_date': convert_date_format(row.get('Contract Date')),
                'contract_payment_plan': row.get('Contract Payment Plan', None),
                'creation_date': convert_date_format(row.get('Creation Date')),
                'contract_value': float(row.get('Contract Value', 0))
                    if row.get('Contract Value') else None,
                'collected_amount': float(row.get('Collected Amount', 0))
                    if row.get('Collected Amount') else None,
                'collected_percent': float(row.get('Collected Percent', 0))
                    if row.get('Collected Percent') else None,

                'contract_delivery_date': convert_date_format(row.get('Contract Delivery Date')),
                'grace_period_months': clean_numeric(row.get('Grace Period Months', '0')),
                'construction_delivery_date': convert_date_format(row.get('Construction Delivery Date')),
                'development_delivery_date': convert_date_format(row.get('Development Delivery Date')),
                'client_handover_date': convert_date_format(row.get('Client Handover Date')),

                'contractor_type': row.get('Contractor Type', None),
                'contractor': row.get('Contractor', None),
                'customer': row.get('Customer', None),
                'broker': row.get('Broker', None),
                'bulks': row.get('Bulks', None),
                'direct_indirect_sales': row.get('Direct Indirect Sales', None),

                'sales_value': float(row.get('Sales Value', 0))
                    if row.get('Sales Value') else None,
                'psm': float(row.get('PSM', 0))
                    if row.get('PSM') else None,
                'area_range': row.get('Area Range', None),
                'release_year': clean_numeric(row.get('Release Year', '0')),
                'sales_year': clean_numeric(row.get('Sales Year', '0')),
                'adj_status': row.get('Adj Status', None),
                'ams': row.get('AMS', None),
            }
        )
