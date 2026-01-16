# ToP/services/company_management_service.py

from django.db.models import Count
from django.shortcuts import get_object_or_404

from ..forms import CompanyForm
from ..models import (
    Company,
    CompanyType,
    CompanyUser,
    CompanyController,
    CompanyManager,
)


class CompanyManagementService:
    """
    One service to support 3 views:
    - create_company
    - upload_company_logo
    - manage_companies
    """

    # ==================================================
    # 1) CREATE COMPANY (from your create_company view)
    # ==================================================
    @staticmethod
    def create_company(*, user, method, post_data, files):
        """
        Creates a company using CompanyForm. 
        ERP Access Key generation logic has been removed.
        """
        if method == "POST":
            form = CompanyForm(post_data, files)

            if form.is_valid():
                company = form.save()

                # Handle comp_type list for the success message
                # JSONField automatically deserializes to a list in the model instance
                types = company.comp_type if isinstance(company.comp_type, list) else []

                # Generic success message listing active modules
                readable_types = [t for t in types if t]
                if readable_types:
                    message = f"Company created successfully with modules: {', '.join(readable_types)}."
                else:
                    message = "Company created successfully."

                # Reset form after success
                return {
                    "form": CompanyForm(),
                    "message": message,
                    "message_level": "success",
                }

            # Show non-field errors as messages
            non_field_errors = form.non_field_errors()
            if non_field_errors:
                return {
                    "form": form,
                    "message": " ".join(str(e) for e in non_field_errors),
                    "message_level": "error",
                }

            return {"form": form}

        # GET request
        return {"form": CompanyForm()}

    # ==================================================
    # 2) UPLOAD COMPANY LOGO (from your upload_company_logo view)
    # ==================================================
    @staticmethod
    def upload_company_logo(*, user, method, company_id, files):
        company = get_object_or_404(Company, id=company_id)

        if method == "POST" and files.get("logo"):
            company.logo = files["logo"]
            company.save(update_fields=["logo"])
            return {
                "message": f"Logo uploaded for {company.name}.",
                "message_level": "success",
            }

        return {"message": None}

    # ==================================================
    # 3) MANAGE COMPANIES
    # ==================================================
    @staticmethod
    def manage_companies(*, user, method, data):
        # ----------------------------------------------
        # 1. Role Resolution
        # ----------------------------------------------
        is_admin_or_dev = (
            user.groups.filter(name__in=["Admin", "Developer"]).exists()
            or user.is_superuser
        )

        is_team_member = (
            not is_admin_or_dev
            and user.groups.filter(name="TeamMember").exists()
        )

        # ----------------------------------------------
        # 2. POST Actions
        # ----------------------------------------------
        if method == "POST":
            action = data.get("action")

            if is_team_member and action in ["save", "delete"]:
                return {
                    "error": "You do not have permission to edit or delete companies.",
                    "redirect": "manage_companies",
                }

            company_id = data.get("company_id")
            company = get_object_or_404(Company, id=company_id)

            if action == "save":
                CompanyManagementService._save_company(company, data)
                CompanyManagementService._sync_company_users(company)
                return {
                    "redirect": "manage_companies",
                    "message": "Company updated successfully!",
                }

            elif action == "delete":
                CompanyManagementService._delete_company(company)
                return {
                    "redirect": "manage_companies",
                    "message": "Company deleted successfully!",
                }

        # ----------------------------------------------
        # 3. GET: Query Companies
        # ----------------------------------------------
        companies_query = Company.objects.annotate(
            project_count=Count("project")
        )

        if is_team_member:
            # Filter by capability (Field Existence)
            companies = companies_query.filter(
                google_sheet_url__isnull=False
            ).exclude(google_sheet_url="")
        else:
            companies = companies_query.all()

        return {
            "companies": companies,
            "is_team_member": is_team_member,
        }

    # ==================================================
    # HELPERS
    # ==================================================
    @staticmethod
    def _save_company(company, data):
        """
        Manually updates company fields from request data.
        Handles the JSON 'comp_type' field.
        """
        company.name = data.get("name")
        company.joining_date = data.get("joining_date")
        company.is_active = (data.get("is_active", "false").lower() == "true")

        # Handle Multi-Select Types (JSONField)
        if hasattr(data, "getlist"):
            posted_types = data.getlist("comp_type")
        else:
            raw = data.get("comp_type")
            posted_types = raw if isinstance(raw, list) else [raw] if raw else []

        # Clean empty strings
        posted_types = [t for t in posted_types if t]
        
        # Default to Native if empty (optional business rule)
        if not posted_types:
            posted_types = [CompanyType.NATIVE]
            
        company.comp_type = posted_types

        # --------------------------------------------------------
        # INDEPENDENT FIELD SAVING
        # --------------------------------------------------------

        # 1. ERP Fields
        if data.get("erp_url"):
            company.erp_url = (data.get("erp_url") or "").strip()
            company.erp_url_units = (data.get("erp_url_units") or "").strip()
            company.erp_url_unit = (data.get("erp_url_unit") or "").strip()
            company.erp_url_leads = (data.get("erp_url_leads") or "").strip()
            company.erp_url_key = (data.get("erp_url_key") or "").strip()
            company.erp_url_units_key = (data.get("erp_url_units_key") or "").strip()
            company.erp_url_unit_key = (data.get("erp_url_unit_key") or "").strip()
            company.erp_url_leads_key = (data.get("erp_url_leads_key") or "").strip()

        # 2. Google Sheet Fields
        if data.get("google_sheet_url"):
            company.google_sheet_url = (data.get("google_sheet_url") or "").strip() or None
            company.google_sheet_gid = (data.get("google_sheet_gid") or "").strip() or None
            company.google_sheet_title = (data.get("google_sheet_title") or "").strip() or None

        company.save()
 
    @staticmethod
    def _sync_company_users(company):
        """Syncs is_active status to all related users."""
        for cu in CompanyUser.objects.filter(company=company):
            cu.user.is_active = company.is_active
            cu.user.save()

        for cc in CompanyController.objects.filter(company=company):
            cc.user.is_active = company.is_active
            cc.user.save()

        for cm in CompanyManager.objects.filter(company=company):
            cm.user.is_active = company.is_active
            cm.user.save()

    @staticmethod
    def _delete_company(company):
        """Deletes company and associated users."""
        for cu in CompanyUser.objects.filter(company=company):
            if cu.user:
                cu.user.delete()
            cu.delete()

        for cc in CompanyController.objects.filter(company=company):
            if cc.user:
                cc.user.delete()
            cc.delete()

        company.delete()