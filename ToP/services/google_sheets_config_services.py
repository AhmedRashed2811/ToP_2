from django.db import transaction
from django.shortcuts import get_object_or_404

from ..models import Company, GoogleServiceAccount
from ..utils.google_sheets_utils import gspread_client, resolve_worksheet


class GoogleServiceAccountManagementService:
    """
    Handles Google Service Account management operations (service layer).

    - Views stay thin.
    - Utils hold Google auth/sheet helpers.
    - This class holds business logic + validation + DB operations.
    """

    # ==================================================
    # PUBLIC ENTRY POINTS
    # ==================================================

    @staticmethod
    def get_service_accounts_data(*, user):
        """
        Retrieves data for the manage service accounts page.
        """
        # UPDATED: Filter by CAPABILITY (has URL), not strict label.
        # This supports the "One or More" company type logic.
        companies = Company.objects.filter(
            google_sheet_url__isnull=False
        ).exclude(
            google_sheet_url=""
        ).order_by("name")
        
        service_accounts = GoogleServiceAccount.objects.select_related("company").all().order_by("company__name")
        return {
            "companies": companies,
            "service_accounts": service_accounts,
        }

    @staticmethod
    def create_or_update_service_account(*, user, company_id, data):
        """
        Creates or updates a Google Service Account for a company.
        Expects 'data' to be a dictionary-like object (e.g., request.POST / QueryDict).
        """
        try:
            if not company_id:
                return {"success": False, "error": "company_id is required"}

            company = get_object_or_404(Company, id=company_id)

            # UPDATED: Sanity check based on FIELD EXISTENCE, not Type Enum.
            if not company.google_sheet_url:
                return {"success": False, "error": "This company does not have a Google Sheet URL configured."}

            required_fields = [
                "project_id",
                "private_key_id",
                "private_key",
                "client_email",
                "client_id",
                "client_x509_cert_url",
            ]

            missing = [f for f in required_fields if not data.get(f)]
            if missing:
                return {"success": False, "error": f"Missing required fields: {', '.join(missing)}"}

            # Normalize private_key in case it comes with escaped newlines
            private_key = (data.get("private_key") or "").replace("\\n", "\n")

            payload = {
                "project_id": data.get("project_id"),
                "private_key_id": data.get("private_key_id"),
                "private_key": private_key,
                "client_email": data.get("client_email"),
                "client_id": data.get("client_id"),
                "client_x509_cert_url": data.get("client_x509_cert_url"),
            }

            with transaction.atomic():
                service_account, created = GoogleServiceAccount.objects.update_or_create(
                    company=company,
                    defaults=payload
                )

            message = f"Google Service Account {'created' if created else 'updated'} successfully for {company.name}"
            return {"success": True, "message": message, "service_account": service_account, "created": created}

        except Exception as e:
            return {"success": False, "error": f"Error creating service account: {str(e)}"}

    @staticmethod
    def test_service_account(*, user, account_id, gspread_client_func=None, resolve_worksheet_func=None):
        """
        Tests if the Google Service Account credentials work by attempting to access the associated Google Sheet.

        You can optionally inject helper funcs for unit tests:
        - gspread_client_func(company) -> gspread client
        - resolve_worksheet_func(sheet, gid, title) -> worksheet
        """
        gspread_client_func = gspread_client_func or gspread_client
        resolve_worksheet_func = resolve_worksheet_func or resolve_worksheet

        service_account = get_object_or_404(GoogleServiceAccount, id=account_id)
        company = service_account.company

        # Respect active flag (your util also checks it, but this gives a clean message early)
        if not service_account.is_active:
            return {"success": False, "status": "error", "message": f"Google Service Account for {company.name} is not active"}

        if not company.google_sheet_url:
            return {"success": False, "status": "error", "message": "Company has no Google Sheet URL configured"}

        try:
            gc = gspread_client_func(company)

            sh = gc.open_by_url(company.google_sheet_url)
            ws = resolve_worksheet_func(sh, company.google_sheet_gid, company.google_sheet_title)

            # Lightweight read (instead of get_all_records which can be huge)
            # Just proves we can access the sheet/worksheet.
            a1_value = None
            try:
                a1_value = ws.acell("A1").value
            except Exception:
                # Some sheets might block cell-level read in weird ways; still having ws.title is a good sign.
                pass

            return {
                "success": True,
                "status": "success",
                "message": f"Successfully connected to {company.name} Google Sheet",
                "spreadsheet_title": sh.title,
                "worksheet_title": ws.title,
                "a1_value": a1_value,
                # Metadata estimates (fast, no full download)
                "row_count_estimate": getattr(ws, "row_count", None),
                "col_count_estimate": getattr(ws, "col_count", None),
            }

        except Exception as e:
            return {"success": False, "status": "error", "message": f"Failed to connect: {str(e)}"}

    @staticmethod
    def toggle_service_account(*, user, account_id):
        """
        Enables or disables a Google Service Account.
        """
        service_account = get_object_or_404(GoogleServiceAccount, id=account_id)

        service_account.is_active = not service_account.is_active
        service_account.save(update_fields=["is_active"])

        status = "enabled" if service_account.is_active else "disabled"
        message = f"Google Service Account for {service_account.company.name} has been {status}"
        return {"success": True, "message": message, "service_account": service_account}