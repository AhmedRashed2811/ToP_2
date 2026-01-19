import json
import requests
import traceback
import logging 

from ToP.utils.utils import _get_uploader_company, _projects_qs_for_user, _get_locked_company_for_uploader

from .services.inventory_sync_service import InventorySyncService
from .services.top_calculation_service import TopCalculationService
from .services.unit_catalog_service import UnitCatalogService

from .services.company_management_services import CompanyManagementService
from .services.csv_inventory_service import CsvInventoryService
from .services.modification_records_service import ModificationRecordsService
from .services.support_email_service import SupportEmailService
from .services.project_service import ProjectManagementService
from .services.google_sheets_config_services import GoogleServiceAccountManagementService
from .services.user_management_services import UserManagementService
from .services.sales_requests_services import SalesRequestManagementService
from .services.units_management_service import UnitsManagementService
from .services.hold_request_service import HoldRequestsManagementService
from .services.saved_units_service import SavedUnitsService
from .services.attendance_service import AttendanceActionService, AttendanceQueryService
from .services.project_web_config_service import ProjectWebConfigService
from .services.extended_payments_service import ProjectExtendedPaymentsService
from .services.special_offers_service import SpecialOffersPaymentsService
from .services.sales_request_analytical_service import SalesRequestAnalyticalService
from .services.inventory_report_service import InventoryReportService
from .services.market_research_master_data_service import MarketResearchMasterDataService
from .services.market_research_units_management_service import MarketResearchUnitsManagmentService
from .services.sales_performance_service import SalesPerformanceService
from .services.unit_mapping_service import UnitMappingService
from .services.home_service import TOPHomeService
from .services.unit_auto_unblock_service import UnitAutoUnblockService
from .services.market_research_service import MarketResearchService
from .services.admin_dashboard_service import AdminDashboardService
from .services.pricing_service import PricingService
from .utils.admin_dashboard_utils import is_superuser_check
from .strategies.inventory_strategy import get_inventory_strategy
from .services.historical_sales_requests_analysis_service import HistoricalSalesRequestsAnalysisService
from .services.unit_warehouse_service import UnitWarehouseService
from .services.import_hub_service import ImportHubService
from .services.sales_team_service import SalesTeamService

from .forms import *
from .models import *
from .decorators import *


from django.shortcuts import render, redirect,get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie   
from django.views.decorators.http import require_POST,require_GET, require_http_methods
from decimal import getcontext



from .utils.viewer_permissions import (
    is_company_viewer,
    viewer_can_access_page,
    PAGE_ToP,
    PAGE_INV_REPORT,
    PAGE_MASTERPLANS,
    PAGE_SALES_PERFORMANCE_ANALYSIS,
)
from django.http import HttpResponseForbidden



# Set up logging
logger = logging.getLogger(__name__)
getcontext().prec = 28  # precision for money math


# ---------------------- Google Auth Helpers ----------------------
 
# ---------------------------------------------- View to manage Google Service Accounts for companies
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def manage_google_service_accounts(request):
    """View to manage Google Service Accounts for companies"""
    # Call the service method
    data = GoogleServiceAccountManagementService.get_service_accounts_data(user=request.user)

    return render(request, 'ToP/manage_google_service_accounts.html', data)


# ---------------------------------------------- Create or update Google Service Account for a company
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@csrf_exempt
def create_google_service_account(request):
    """Create or update Google Service Account for a company"""
    if request.method == 'POST':
        # Call the service method with POST data
        result = GoogleServiceAccountManagementService.create_or_update_service_account(
            user=request.user,
            company_id=request.POST.get('company_id'),
            data=request.POST # Pass the QueryDict directly
        )

        if result["success"]:
            messages.success(request, result["message"])
        else:
            messages.error(request, result["error"])

        return redirect('manage_google_service_accounts')

    return redirect('manage_google_service_accounts')


@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@csrf_exempt
def test_google_service_account(request, account_id):
    """Test if Google Service Account credentials work"""
    # Call the service method, passing the gspread utility functions
    result = GoogleServiceAccountManagementService.test_service_account(
        user=request.user,
        account_id=account_id
    )
    return JsonResponse(result)


# ---------------------------------------------- Enable/disable Google Service Account
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@csrf_exempt
def toggle_google_service_account(request, account_id):
    """Enable/disable Google Service Account"""
    # Call the service method
    result = GoogleServiceAccountManagementService.toggle_service_account(
        user=request.user,
        account_id=account_id
    )

    if result["success"]:
        messages.success(request, result["message"])

    return redirect('manage_google_service_accounts')



# ============================== CRUD / PAGES ==============================
 
# ------------------------------------------------------------------------------ Create Company

@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def create_company(request):
    result = CompanyManagementService.create_company(
        user=request.user,
        method=request.method,
        post_data=request.POST,
        files=request.FILES,
    )

    if result.get("message"):
        level = result.get("message_level", "success")
        getattr(messages, level)(request, result["message"])

    return render(
        request,
        "ToP/create_company.html",
        {
            "form": result["form"],
            "generated_key": result.get("generated_key"),
        },
    )


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer"])
def upload_company_logo(request, company_id):
    result = CompanyManagementService.upload_company_logo(
        user=request.user,
        method=request.method,
        company_id=company_id,
        files=request.FILES,
    )

    if result.get("message"):
        level = result.get("message_level", "success")
        getattr(messages, level)(request, result["message"])

    return redirect("manage_companies")


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def manage_companies(request):
    result = CompanyManagementService.manage_companies(
        user=request.user,
        method=request.method,
        # PASS RAW POST (QueryDict) TO PRESERVE LISTS FOR MULTI-SELECT
        data=request.POST, 
    )

    if "error" in result:
        messages.error(request, result["error"])
        return redirect(result.get("redirect", "manage_companies"))

    if "redirect" in result:
        messages.success(request, result.get("message", "Company updated successfully!"))
        return redirect(result["redirect"])

    return render(request, "ToP/manage_companies.html", result)
# ============================== GOOGLE SHEETS: SYNC ==============================
 



# ---------------------------------------------- DELETE all Units for the given company, then IMPORT from its Google Sheet.

@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_POST
def sync_company_units_from_sheet(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    result = InventorySyncService.sync_company(company)
    return JsonResponse(
        result.to_dict(),
        status=200 if result.success else 400
    )



@login_required(login_url="login")
def home(request):
    # preserve: auto-unblock runs at the start
    UnitAutoUnblockService.run()

    # preserve: SalesOperation redirect
    if request.user.groups.filter(name="SalesOperation").exists():
        return redirect("sales_requests_list")
    
    if request.user.groups.filter(name="Uploader").exists():
        return redirect("project_web_config") 
    
    if request.user.groups.filter(name="CompanyAdmin").exists():
        return redirect("manage_users") 
    
    # Viewer gate: must have "TOP" allowed in JSON
    if is_company_viewer(request.user) and not viewer_can_access_page(request.user, PAGE_ToP):
        return HttpResponseForbidden("You are not authorized to view this page.")


    # View owns request handling
    unit_query = request.POST.get("unit_code", "")
    project_query = request.POST.get("project_name", "")

    result = TOPHomeService.build_home_response(
        user=request.user,
        session=request.session,
        method=request.method,
        unit_query=unit_query,
        project_query=project_query,
        messages_api=messages,
        request_for_messages=request,
        # keep request only if you truly need messages in utils;
        # but per your requirement: service should not receive request
        # so messages handling will be done inside utils via passed-in "messages_api"
    )

    if result.get("_type") == "redirect":
        return redirect(result["to"])

    return render(request, result["template"], result["context"])


@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Sales", "Manager", "SalesHead", "Viewer"])
@viewer_page_required(PAGE_MASTERPLANS)
def unit_catalog_view(request):
    # combine GET + POST params safely
    params = request.GET if request.method == "GET" else request.POST

    ctx = UnitCatalogService.build_context(
        user=request.user,
        params=params,
    )

    # Optional: show forbidden page message
    if ctx.get("forbidden"):
        return HttpResponseForbidden("You are not authorized to access Unit Catalog.")

    return render(request, "ToP/unit_catalog.html", ctx)




@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer"])
def modification_records_view(request):
    context = ModificationRecordsService().build_view_context()
    return render(request, "ToP/modification_records.html", context)


# -------------------------------------------------------------------------------------------------------------------------------- Main Function


# ---------------------------------------------- Login
@unauthenticated_user
def login(request):
    result = UserManagementService.login(
        method=request.method,
        post_data=request.POST,
        request=request,  # needed to call auth login + session handling
    )

    if result.get("redirect"):
        return redirect(result["redirect"])

    return render(request, "ToP/login.html", result.get("context", {}))


# ---------------------------------------------- Logout
@login_required(login_url="login")
def logout(request):
    UserManagementService.logout(request=request)
    return redirect("login")


# ---------------------------------------------- Change Password
@login_required(login_url="login")
def change_password(request):
    result = UserManagementService.change_password(
        user=request.user,
        method=request.method,
        post_data=request.POST,
        request=request,
    )

    if result.get("message"):
        level = result.get("message_level", "success")
        getattr(messages, level)(request, result["message"])

    if result.get("redirect"):
        return redirect(result["redirect"])

    return render(request, "ToP/change_password.html", result["context"])


# ---------------------------------------------- Create User
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "CompanyAdmin"])
def create_user(request):
    result = UserManagementService.create_user(
        actor=request.user,
        method=request.method,
        post_data=request.POST,
    )

    for m in result.get("messages", []):
        getattr(messages, m["level"])(request, m["text"])

    if result.get("redirect"):
        return redirect(result["redirect"])

    return render(request, "ToP/create_user.html", result["context"])


# ---------------------------------------------- Login As User (Impersonation)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin"])  # CompanyAdmin must NEVER access impersonation
def login_as_user(request):
    result = UserManagementService.login_as_user(
        actor=request.user,
        method=request.method,
        post_data=request.POST,
        request=request,
    )

    for m in result.get("messages", []):
        getattr(messages, m["level"])(request, m["text"])

    return redirect(result.get("redirect", "manage_users"))


# ---------------------------------------------- Manage Users
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "CompanyAdmin"])  # ✅ UPDATED
def manage_users(request):
    result = UserManagementService.manage_users(
        actor=request.user,
        method=request.method,
        post_data=request.POST,
        request=request,
    )

    # If AJAX, the service returns JsonResponse directly:
    if isinstance(result, JsonResponse):
        return result

    # ✅ if service says redirect
    if result.get("redirect"):
        for m in result.get("messages", []):
            messages.add_message(
                request,
                messages.SUCCESS if m["level"] == "success" else
                messages.WARNING if m["level"] == "warning" else
                messages.ERROR,
                m["text"],
            )
        return redirect(result["redirect"])

    # ✅ GET (or POST falling through) must render
    context = result.get("context", {})
    for m in result.get("messages", []):
        messages.add_message(
            request,
            messages.SUCCESS if m["level"] == "success" else
            messages.WARNING if m["level"] == "warning" else
            messages.ERROR,
            m["text"],
        )

    return render(request, "ToP/manage_users.html", context)


# ---------------------------------------------- Import Sales Users (CSV)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "CompanyAdmin"])
@csrf_exempt
def import_company_users(request):
    result = UserManagementService.import_company_users(
        actor=request.user,
        method=request.method,
        files=request.FILES,
        post_data=request.POST,
    )
    return JsonResponse(result["payload"], status=result["status"])


# ---------------------------------------------- Revert Impersonation
@login_required(login_url="login")
def revert_impersonation(request):
    result = UserManagementService.revert_impersonation(request=request)

    for m in result.get("messages", []):
        getattr(messages, m["level"])(request, m["text"])

    return redirect(result.get("redirect", "manage_users"))


# ---------------------------------------------- Sales Teams
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "CompanyAdmin"])
def sales_teams(request):
    result = SalesTeamService.sales_teams(
        actor=request.user,
        method=request.method,
        post_data=request.POST,
    )

    for m in result.get("messages", []):
        getattr(messages, m["level"])(request, m["text"])

    if result.get("redirect"):
        return redirect(result["redirect"])

    return render(request, "ToP/sales_teams.html", result["context"])



# -------------------------------------------------------------------------
# BACKGROUND TASK: Process CSV (optional compatibility wrapper)
# -------------------------------------------------------------------------

@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def get_upload_progress(request):
    task_id = request.GET.get("task_id")
    return JsonResponse(CsvInventoryService.get_progress(task_id))


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def upload_csv(request):
    companies = Company.objects.filter(comp_type__contains="native")

    if request.method == "POST" and request.FILES.get("csv_file"):
        response = CsvInventoryService.start_upload(
            user=request.user,
            files=request.FILES,
            data=request.POST.dict(),
        )
        if response:
            return response

    return render(request, "ToP/upload_csv.html", {"companies": companies})



# ---------------------------------------------- Units Data
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "SalesOperation", "Controller", "Uploader"])
def units_data(request):
    user = request.user
    company = None

    # Treat Uploader exactly like Manager (company-scoped)
    uploader_company = _get_uploader_company(user)

    if request.user.groups.filter(name="Manager").exists():
        user_manager = Manager.objects.filter(user=user).first()
        company = user_manager.company if user_manager else None

    elif uploader_company is not None:
        company = uploader_company

    elif request.user.groups.filter(name__in=["Controller", "SalesOperation"]).exists():
        # Preserving your current behavior (Controller uses SalesOperation model)
        user_ops = SalesOperation.objects.filter(user=user).first()
        company = user_ops.company if user_ops else None

    editable_fields = []
    if request.user.groups.filter(name="SalesOperation").exists():
        ops = SalesOperation.objects.filter(user=request.user).only("editable_unit_fields").first()
        editable_fields = (ops.editable_unit_fields or []) if ops else []

    return render(
        request,
        "ToP/units_data.html",
        {
            "company": company,
            "editable_fields": editable_fields,
        },
    )


# ---------------------------------------------- Returns all units as JSON for frontend filtering
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "SalesOperation", "Controller", "Uploader"])
def units_list(request):
    data = UnitsManagementService.get_units(user=request.user)
    return JsonResponse(data, safe=False)


# ---------------------------------------------- Updates a specific field of a unit in the database
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "SalesOperation", "Controller", "Uploader"])
@csrf_exempt
@require_POST
def update_unit(request):
    try:
        data = json.loads(request.body)

        result = UnitsManagementService.update_unit_field(
            user=request.user,
            unit_code=data.get("unit_code"),
            field=data.get("field"),
            value=data.get("value"),
        )

        return JsonResponse(result["payload"], status=result["status"])

    except Exception as e:
        logger.error(f"update_unit error: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
    
    

@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
def import_hub(request):
    """
    Renders the Import Hub Dashboard.

    Behavior:
    - If user is Uploader with a related company => auto-lock their company
      and do not expose any other companies.
    - Else (Admin/Developer/TeamMember) => show all companies and allow selecting.
    """
    company = None
    locked_company = _get_locked_company_for_uploader(request.user)
    is_uploader = bool(locked_company)

    # Uploader: only their own company
    if is_uploader:
        companies = Company.objects.filter(id=locked_company.id)
        company = companies.first()
    else:
        companies = Company.objects.all()

    company_configs = {}
    for c in companies:
        types = c.comp_type if isinstance(c.comp_type, list) else ([c.comp_type] if c.comp_type else [])

        company_configs[c.id] = {
            "has_erp": ("erp" in types) or bool(c.erp_url),
            "has_sheets": ("google_sheets" in types) or bool(c.google_sheet_url),
            "has_csv": True,
            "erp_url": c.erp_url,
            "sheet_url": c.google_sheet_url,
        }

    context = {
        "companies": companies,
        "company_configs": json.dumps(company_configs),
        "is_uploader": is_uploader,
        "company":company, 
        "locked_company_id": locked_company.id if locked_company else "",
        "locked_company_name": locked_company.name if locked_company else "",
    }
    return render(request, "ToP/import_hub.html", context)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
@require_POST
def trigger_unified_import(request):
    """
    AJAX: Triggers import (ERP/Sheet/CSV) via UnitWarehouseService.

    - If user is Uploader => company is auto-locked (ignore posted company_id).
    - Else => company_id required.
    """
    try:
        source_type = request.POST.get("source_type")
        if not source_type:
            return JsonResponse({"success": False, "error": "Missing parameters"})

        locked_company = _get_locked_company_for_uploader(request.user)

        if locked_company:
            company = locked_company
        else:
            company_id = request.POST.get("company_id")
            if not company_id:
                return JsonResponse({"success": False, "error": "Missing parameters"})
            company = get_object_or_404(Company, id=company_id)

        csv_file = request.FILES.get("csv_file")

        result = UnitWarehouseService.trigger_import(
            company=company,
            source_type=source_type,
            file_data=csv_file,
        )
        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Import Error: {e}")
        return JsonResponse({"success": False, "error": str(e)})


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
@require_POST
def delete_hub_units(request):
    """
    AJAX: Deletes units via ImportHubService.
    Expects JSON: { "company_id": 1, "unit_codes": ["U1", "U2"] }

    - If user is Uploader => company is auto-locked (ignore body company_id).
    - Else => uses provided company_id.
    """
    try:
        data = json.loads(request.body or "{}")
        unit_codes = data.get("unit_codes", [])

        locked_company = _get_locked_company_for_uploader(request.user)

        if locked_company:
            company_id = locked_company.id
        else:
            company_id = data.get("company_id")

        result = ImportHubService.delete_units_bulk(
            company_id=company_id,
            unit_codes=unit_codes,
        )
        return JsonResponse(result)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"})
    except ValueError as e:
        return JsonResponse({"success": False, "error": str(e)})
    except Exception as e:
        logger.error(f"Delete Units Error: {e}")
        return JsonResponse({"success": False, "error": str(e)})





@login_required(login_url='login')
def sales_requests_demo(request):
    """
    Renders the frontend-only demonstration of the sales dashboard.
    All logic (timers, actions, toasts) is handled via JavaScript in the template.
    """
    context = {
        # We pass this just in case base.html relies on it
        'is_impersonating': request.session.get('impersonator_id') is not None,
    }
    return render(request, 'ToP/demo_sales_requests.html', context)



@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "SalesOperation", "Manager"])
def sales_requests_list(request):
    is_impersonating = request.session.get("impersonator_id") is not None

    result = SalesRequestManagementService.get_sales_requests_list_context(
        user=request.user,
        is_impersonating=is_impersonating,
    )

    if not result["success"]:
        # keep it simple: show empty page or return an error page
        return render(request, "ToP/sales_requests_list.html", {
            "sales_requests": [],
            "is_impersonating": is_impersonating,
            "erp": False,
            "company": None,
            "major_project_config": None,
            "error": result["error"],
        })

    context = result["data"]
    return render(request, "ToP/sales_requests_list.html", context)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "SalesOperation", "Manager"])
def delete_sales_request(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)
        request_id = data.get("request_id")
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON payload"}, status=400)

    # REMOVED: requests_post_func=requests.post
    # The service now handles the API call internally
    result = SalesRequestManagementService.delete_sales_request(
        user=request.user,
        request_id=request_id,
    )
    
    return JsonResponse(result["payload"], status=result["status"])


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "SalesOperation", "Manager"])
def apply_discount(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)
        request_id = data.get("request_id")
        discount_percentage = data.get("discount_percentage")
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON payload"}, status=400)

    result = SalesRequestManagementService.apply_discount(
        user=request.user,
        request_id=request_id,
        discount_percentage=discount_percentage,
    )
    return JsonResponse(result["payload"], status=result["status"])


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "SalesOperation", "Manager"])
@require_POST
def extend_sales_request(request):
    try:
        data = json.loads(request.body)
        request_id = data.get("request_id")
        minutes_to_add = int(data.get("minutes", 0))
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON payload"}, status=400)

    result = SalesRequestManagementService.extend_sales_request(
        user=request.user,
        request_id=request_id,
        minutes_to_add=minutes_to_add,
    )
    return JsonResponse(result["payload"], status=result["status"])


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "SalesOperation", "Manager"])
@require_GET
def get_timer_status(request):
    result = SalesRequestManagementService.get_timer_status(user=request.user)
    return JsonResponse(result["payload"], status=result["status"])


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "SalesOperation", "Manager"])
def approve_sales_request(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)
        request_id = data.get("request_id")
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON payload"}, status=400)

    # REMOVED: requests_post_func=requests.post
    # The service now handles the request internally
    result = SalesRequestManagementService.approve_sales_request(
        user=request.user,
        request_id=request_id,
        logger=logger,
    )
    
    return JsonResponse(result["payload"], status=result["status"])

@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "SalesOperation", "Manager"])
def download_sales_pdf(request):
    # Note: GET parameter is named 'unit_code' but actually carries SalesRequest ID
    request_id = request.GET.get("unit_code")
    return SalesRequestManagementService.build_and_render_sales_pdf_response(
        request_id=str(request_id)
    )


# ---------------------------------------------- Create Project
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
def create_project(request):
    if request.method == 'POST':
        result = ProjectManagementService.create_project(
            user=request.user,
            data=request.POST,
            files=request.FILES
        )

        if result["success"]:
            messages.success(request, result["message"])
            return redirect('create_project')

        # --- KEEP YOUR ERROR HANDLING EXACTLY AS-IS ---
        errors = result.get("errors", {})
        if errors:
            print(f"DEBUG: Errors returned from service: {errors}")
            for field, error_list in errors.items():
                if isinstance(error_list, list):
                    for error in error_list:
                        error_message = f"{field.replace('_', ' ').title()}: {error}" if field != '__all__' else error
                        messages.error(request, error_message)
                else:
                    error_message = f"{field.replace('_', ' ').title()}: {error_list}" if field != '__all__' else error_list
                    messages.error(request, error_message)
        else:
            messages.error(request, "Error creating project. Please check the form.")

        # Rebuild context (POST-bound), now scoped for uploader if needed
        context = ProjectManagementService.build_create_view_context(
            user=request.user,
            data=request.POST,
            files=request.FILES
        )
        return render(request, 'ToP/create_project.html', context)

    # GET
    context = ProjectManagementService.build_create_view_context(user=request.user)
    return render(request, 'ToP/create_project.html', context)


# ---------------------------------------------- Project Dashboard
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
def project_dashboard(request):
    # ✅ Scope by uploader company if applicable
    projects = ProjectManagementService.get_projects_for_user(request.user)
    companies = ProjectManagementService.get_companies_for_user(request.user)
    company = None

    # logic: Check if user is in Admin or Developer groups OR is a superuser
    can_delete = request.user.groups.filter(name__in=["Admin", "Uploader"]).exists() or request.user.is_superuser
    is_uploader = request.user.groups.filter(name__in=["Uploader"]).exists()
    if is_uploader:
        company = request.user.uploader_profile.company
        
    context = {
        "projects": projects,
        "companies": companies,
        "can_delete": can_delete,
        "company":company, 
        # flags used by the template (for hiding company filter, etc.)
        **ProjectManagementService.get_user_scope_flags(request.user),
    }
    return render(request, "ToP/project_dashboard.html", context)


# ---------------------------------------------- Delete Project
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader"])
def delete_project(request, project_id):
    result = ProjectManagementService.delete_project(
        user=request.user,
        project_id=project_id
    )

    if result["success"]:
        messages.success(request, result["message"])
    else:
        messages.error(request, result.get("errors", {}).get("__all__", ["An error occurred"])[0])

    return redirect("project_dashboard")


# ---------------------------------------------- Update Project
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
@csrf_exempt
def update_project(request, project_id):
    if request.method == "POST":
        try:
            if request.content_type.startswith('multipart/form-data'):
                data_str = request.POST.get('data')
                if not data_str:
                    return JsonResponse({"success": False, "error": "No data provided in FormData"}, status=400)
                structured_data = json.loads(data_str)
                masterplan_image = request.FILES.get('masterplan_image')
                files_to_pass = {'masterplan_image': masterplan_image} if masterplan_image else None
            else:
                structured_data = json.loads(request.body)
                files_to_pass = None

            # ✅ Service enforces uploader scoping (can’t update other companies)
            result = ProjectManagementService.update_project(
                user=request.user,
                project_id=project_id,
                structured_data=structured_data,
                files=files_to_pass
            )

            if result["success"]:
                return JsonResponse({"success": True, "message": result["message"]})
            else:
                error_message = result.get("errors", {}).get("__all__", [result.get("error", "An unknown error occurred in the service")])[0]
                return JsonResponse({"success": False, "error": error_message}, status=400)

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON data: {str(e)}"
            print(f"DEBUG: JSON Decode Error in update_project: {error_msg}")
            return JsonResponse({"success": False, "error": error_msg}, status=400)
        except ValidationError as ve:
            error_msg = f"Validation Error: {str(ve)}"
            print(f"DEBUG: ValidationError in update_project: {error_msg}")
            return JsonResponse({"success": False, "error": error_msg}, status=400)
        except Exception as e:
            error_msg = f"An unexpected error occurred: {str(e)}"
            print(f"DEBUG: Unexpected Error in update_project: {error_msg}")
            traceback.print_exc()
            return JsonResponse({"success": False, "error": error_msg}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


# ---------------------------------------------- Remove Masterplan
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
@csrf_exempt
def remove_masterplan(request, project_id):
    if request.method == "POST":
        result = ProjectManagementService.remove_masterplan(
            user=request.user,
            project_id=project_id
        )
        if result["success"]:
            return JsonResponse({"success": True, "message": result["message"]})
        else:
            status_code = 404 if "not found" in result["error"].lower() else 400
            return JsonResponse({"success": False, "error": result["error"]}, status=status_code)
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


# ---------------------------------------------- Delete Npv
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
@csrf_exempt
def delete_npv(request, npv_id):
    if request.method == "DELETE":
        result = ProjectManagementService.delete_npv(user=request.user, npv_id=npv_id)
        if result["success"]:
            return JsonResponse({"success": True, "message": result["message"]})
        else:
            status_code = 404 if "not found" in result["error"].lower() else 400
            return JsonResponse({"success": False, "error": result["error"]}, status=status_code)
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


# ---------------------------------------------- Delete Gas Fee
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
@csrf_exempt
def delete_gas_fee(request, fee_id):
    if request.method == "DELETE":
        result = ProjectManagementService.delete_gas_fee(user=request.user, fee_id=fee_id)
        if result["success"]:
            return JsonResponse({"success": True, "message": result["message"]})
        else:
            status_code = 404 if "not found" in result["error"].lower() else 400
            return JsonResponse({"success": False, "error": result["error"]}, status=status_code)
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


# ---------------------------------------------- Delete Gas Offset
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
@csrf_exempt
def delete_gas_offset(request, offset_id):
    if request.method == "DELETE":
        result = ProjectManagementService.delete_gas_offset(user=request.user, offset_id=offset_id)
        if result["success"]:
            return JsonResponse({"success": True, "message": result["message"]})
        else:
            status_code = 404 if "not found" in result["error"].lower() else 400
            return JsonResponse({"success": False, "error": result["error"]}, status=status_code)
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


# ---------------------------------------------- Delete Maintenance Offset
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
@csrf_exempt
def delete_maintenance_offset(request, offset_id):
    if request.method == "DELETE":
        result = ProjectManagementService.delete_maintenance_offset(user=request.user, offset_id=offset_id)
        if result["success"]:
            return JsonResponse({"success": True, "message": result["message"]})
        else:
            status_code = 404 if "not found" in result["error"].lower() else 400
            return JsonResponse({"success": False, "error": result["error"]}, status=status_code)
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


# ---------------------------------------------- Delete CTD
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
@csrf_exempt
def delete_ctd(request, ctd_id):
    if request.method == "DELETE":
        result = ProjectManagementService.delete_ctd(user=request.user, ctd_id=ctd_id)
        if result["success"]:
            return JsonResponse({"success": True, "message": result["message"]})
        else:
            status_code = 404 if "not found" in result["error"].lower() else 400
            return JsonResponse({"success": False, "error": result["error"]}, status=status_code)
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


# ---------------------------------------------- Delete Maintenance Schedule
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Uploader", "TeamMember"])
@csrf_exempt
def delete_maintenance_schedule(request, schedule_id):
    if request.method == "POST":
        result = ProjectManagementService.delete_maintenance_schedule(user=request.user, schedule_id=schedule_id)
        if result["success"]:
            return JsonResponse({"success": True, "message": result["message"]})
        else:
            status_code = 404 if "not found" in result["error"].lower() else 400
            return JsonResponse({"success": False, "error": result["error"]}, status=status_code)
    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)




@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "Sales", "SalesOperation", "SalesHead"])
def send_support_email(request):
    if request.method == "POST":
        sender_email = request.POST.get("sender_email")
        message_body = request.POST.get("message")

        service = SupportEmailService()
        is_valid, cleaned_sender, cleaned_message = service.validate(sender_email, message_body)

        if is_valid:
            service.send_support_email(cleaned_sender, cleaned_message)
            messages.success(request, "Your message has been sent to the technical support team.")
        else:
            messages.error(request, "All fields are required.")

    return redirect(request.META.get("HTTP_REFERER", "/"))




# ---------------------------------------------- Submit Data
@login_required(login_url='login')
@allowed_users(allowed_roles=["Sales", "Manager", "TeamMember", "Admin", "Developer", "SalesHead", "Viewer"])
def submit_data(request):
    if request.method != "POST":
        return redirect("home")

    result = TopCalculationService.calculate(
        user=request.user,
        data=request.POST.dict(),
    )
    
    if result.get("force_logout"):
        UserManagementService.logout(request=request)
        return render(request, "ToP/login.html")

    return JsonResponse(result)







# ---------------------------------------------- Send Hold To Erp
@login_required(login_url="login")
@allowed_users(allowed_roles=["Sales", "SalesHead"])
@csrf_exempt
def send_hold_to_erp(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "Invalid JSON body"}, status=400)

    result = HoldRequestsManagementService.send_hold_to_erp(
        user=request.user,
        payload=data,
    )

    return JsonResponse(result["payload"], status=result["status"])


# ---------------------------------------------- Save Unit To Session
@login_required(login_url="login")
@allowed_users(allowed_roles=["Sales", "SalesHead"])
def save_unit_to_session(request):
    if request.method != "POST":
        return redirect("home")

    result = HoldRequestsManagementService.save_unit_to_session(
        user=request.user,
        post_data=request.POST,
    )

    # Apply messages in the VIEW (NOT in service)
    for m in result.get("messages", []):
        level = m.get("level", "info")
        text = m.get("text", "")
        getattr(messages, level, messages.info)(request, text)

    # Apply session mutations in the VIEW
    for op in result.get("session_ops", []):
        if op.get("op") == "append":
            key = op["key"]
            request.session.setdefault(key, []).append(op["value"])
            request.session.modified = True

    # Hard HTTP error
    if result.get("http_error"):
        status, msg = result["http_error"]
        return HttpResponse(msg, status=status)

    return redirect(result.get("redirect", "home"))



# ---------------------------------------------- Download All Units Pdf
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "Sales", "SalesHead"])
def download_all_units_pdf(request):
    saved_units = request.session.get("saved_units", [])

    result = SavedUnitsService.build_all_units_pdf(
        saved_units=saved_units,
        template_path="pdf/unit_table_xhtml2pdf.html",
    )

    if not result["success"]:
        # Preserve the old debug behavior
        html = result.get("error_html", "")
        return HttpResponse("We had some errors <pre>" + html + "</pre>")

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{result["filename"]}"'
    response.write(result["pdf_bytes"])
    return response


# ---------------------------------------------- Clear Saved Units
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "Sales", "SalesHead"])
def clear_saved_units(request):
    result = SavedUnitsService.clear_saved_units()

    # Apply session ops (view owns session)
    for op in result.get("session_ops", []):
        if op["op"] == "delete":
            key = op["key"]
            if key in request.session:
                del request.session[key]
                request.session.modified = True

    return redirect(result.get("redirect", "home"))







# ---------------------------------------------- Project Web Config (Page)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Uploader"])  # keep as-is (or add "Uploader" if needed)
def project_web_config(request):
    selected_project_id = request.GET.get("project")

    ctx_result = ProjectWebConfigService.get_page_context(
        user=request.user,
        selected_project_id=selected_project_id
    )

    if not ctx_result.success:
        return render(request, "ToP/project_web_config_form.html", {})

    if request.method == "POST":
        project_id = request.POST.get("project")
        if not project_id:
            messages.error(request, "Project is required.")
            return redirect("/project_web_config/")

        payment_schemes_list = request.POST.getlist("payment_schemes")
        allowed_years_list = request.POST.getlist("allowed_years_for_sales")

        save_result = ProjectWebConfigService.save_config(
            user=request.user,
            project_id=int(project_id),
            post_dict=request.POST,
            payment_schemes_list=payment_schemes_list,
            allowed_years_list=allowed_years_list,
            redirect_after_save=True,
        )

        if save_result.success and save_result.message:
            messages.success(request, save_result.message)

        if save_result.redirect_url:
            return redirect(save_result.redirect_url)

        return redirect("/project_web_config/")

    return render(request, "ToP/project_web_config_form.html", ctx_result.payload)


# ---------------------------------------------- Get Project Web Config (AJAX)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Uploader"])
def get_project_web_config(request, project_id):
    result = ProjectWebConfigService.get_config_json(
        user=request.user,
        project_id=int(project_id)
    )
    if not result.success:
        return JsonResponse({"success": False, "error": result.error}, status=result.status)
    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Save Project Web Config (AJAX)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Uploader"])
@csrf_exempt
def save_project_web_config(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)

    project_id = request.POST.get("project")
    if not project_id:
        return JsonResponse({"success": False, "error": "Project not found"}, status=400)

    payment_schemes_list = request.POST.getlist("payment_schemes")
    allowed_years_list = request.POST.getlist("allowed_years_for_sales")

    result = ProjectWebConfigService.save_config(
        user=request.user,
        project_id=int(project_id),
        post_dict=request.POST,
        payment_schemes_list=payment_schemes_list,
        allowed_years_list=allowed_years_list,
        redirect_after_save=False,
    )

    if not result.success:
        return JsonResponse({"success": False, "error": result.error}, status=result.status)

    return JsonResponse(result.payload, status=result.status)






# ========== STANDARD ==========




# ----------------------------------------------
# Dual Payments Input
@login_required(login_url='login')
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
def dual_payments_input(request):
    projects = _projects_qs_for_user(request.user)
    year_range = range(1, 13)  # Years from 1 to 12

    return render(request, 'ToP/dual_payments.html', {
        'projects': projects,
        'row_range': range(50),
        'year_range': year_range,
        # Optional (if you want to show company name in template for uploader)
        'company': _get_uploader_company(request.user),
    })


# ----------------------------------------------
# Save Extended Payment Ajax
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
@csrf_exempt
def save_extended_payment_ajax(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    result = ProjectExtendedPaymentsService.save(user=request.user, payload=payload)
    return JsonResponse(result.payload, status=result.status)


# ----------------------------------------------
# Fetch Extended Payment Ajax
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
@require_GET
def fetch_extended_payment_ajax(request):
    project_id = request.GET.get("project_id")
    year = int(request.GET.get("year", 1))
    scheme = request.GET.get("scheme", "flat")

    result = ProjectExtendedPaymentsService.fetch(
        user=request.user,
        project_id=int(project_id),
        year=year,
        scheme=scheme,
    )
    return JsonResponse(result.payload, status=result.status)


# ----------------------------------------------
# Delete Extended Payment Ajax
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
@csrf_exempt
def delete_extended_payment_ajax(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    result = ProjectExtendedPaymentsService.delete(user=request.user, payload=payload)
    return JsonResponse(result.payload, status=result.status)


# =========================================================
# SPECIAL OFFERS
# =========================================================

# ----------------------------------------------
# Special Offers Input
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
def special_offers_input(request):
    projects = _projects_qs_for_user(request.user)
    year_range = range(1, 13)  # 1..12

    return render(
        request,
        "ToP/special_offers.html",
        {
            "projects": projects,
            "year_range": year_range,
            "row_range": range(50),
            "pmt_range": range(1, 49),
            # Optional (if you want to show company name in template for uploader)
            "company": _get_uploader_company(request.user),
        },
    )


# ----------------------------------------------
# Save Special Offer Payment Ajax
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
@csrf_exempt
def save_special_offer_payment_ajax(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    result = SpecialOffersPaymentsService.save(user=request.user, payload=payload)
    return JsonResponse(result.payload, status=result.status)


# ----------------------------------------------
# Fetch Special Offer Payment Ajax
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
@require_GET
def fetch_special_offer_payment_ajax(request):
    project_id = request.GET.get("project_id")
    year = request.GET.get("year")

    try:
        project_id = int(project_id)
        year = int(year)
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid project_id or year"}, status=400)

    result = SpecialOffersPaymentsService.fetch(user=request.user, project_id=project_id, year=year)
    return JsonResponse(result.payload, status=result.status)


# ----------------------------------------------
# Delete Special Offer Payment Ajax
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
@csrf_exempt
def delete_special_offer_payment_ajax(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method"})

    try:
        payload = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "message": "Invalid JSON"}, status=400)

    result = SpecialOffersPaymentsService.delete(user=request.user, payload=payload)
    return JsonResponse(result.payload, status=result.status)




# ---------------------------------------------- Sales Dashboard
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "Manager"])
def sales_dashboard(request):
    result = SalesRequestAnalyticalService.get_sales_dashboard_context(user=request.user)
    return render(request, "ToP/sales_dashboard.html", result.payload)


# ---------------------------------------------- Sales Data Api
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "Manager"])
def sales_data_api(request):
    result = SalesRequestAnalyticalService.get_sales_data(user=request.user)
    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Get Projects Salesmen
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "Manager"])
def get_projects_salesmen(request):
    company_id = request.GET.get("company_id")
    try:
        company_id = int(company_id) if company_id else None
    except Exception:
        company_id = None

    result = SalesRequestAnalyticalService.get_projects_and_salesmen(
        user=request.user,
        company_id=company_id,
    )
    return JsonResponse(result.payload, status=result.status)




# ---------------------------------------------- Inventory Model
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "Viewer"])
def inventory_model(request):
    if is_company_viewer(request.user) and not viewer_can_access_page(request.user, PAGE_INV_REPORT):
        return HttpResponseForbidden("You are not authorized to view this page.")

    result = InventoryReportService.get_inventory_dashboard_context(user=request.user)
    return render(request, "ToP/inventory_dashboard.html", result.payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "Viewer"])
def get_company_units(request):
    company_id = request.GET.get("company_id")
    try:
        company_id = int(company_id) if company_id else None
    except Exception:
        company_id = None

    if not company_id:
        return JsonResponse({"units": []}, status=200)

    result = InventoryReportService.get_company_units(
        company_id=company_id,
        inventory_strategy_factory=get_inventory_strategy,
    )
    return JsonResponse(result.payload, status=result.status)

 
 
 
 

# ---------------------------------------------- Market Research Model Master Data View
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_http_methods(["GET"])
def market_research_model_master_data_view(request):
    result = MarketResearchMasterDataService.get_master_data_context()

    if not result.success:
        return JsonResponse({"success": False, "error": result.error or "Unexpected error"}, status=result.status)

    return render(request, "ToP/market_research_model.html", result.payload)


# ---------------------------------------------- Save Market Research Entry
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_POST
def save_market_research_entry(request):
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    model_name = body.get("model")
    value = body.get("value")

    result = MarketResearchMasterDataService.create_entry(model_name=model_name, value=value)

    if not result.success:
        return JsonResponse({"error": result.error or "Invalid request"}, status=result.status)

    # preserve original response shapes
    return JsonResponse(result.payload, status=result.status)



# ---------------------------------------------- Delete Market Research Entry
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_http_methods(["DELETE"])
def delete_market_research_entry(request):
    try:
        try:
            body = json.loads(request.body or "{}")
        except Exception as e:
            print("❌ Invalid JSON body in delete_market_research_entry:", str(e))
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        model_name = body.get("model")
        obj_id = body.get("id")

        result = MarketResearchMasterDataService.delete_entry(
            model_name=model_name,
            obj_id=obj_id,
        )

        if not result.success:
            # ✅ Print the real reason (this is what you want)
            print(
                "❌ MarketResearch delete_entry failed:",
                f"model={model_name}, id={obj_id}, status={result.status}, error={result.error}"
            )
            # Optional: include details to frontend (only if you want)
            # return JsonResponse({"error": result.error or "Invalid request"}, status=result.status)

            # Keep your current frontend behavior:
            return JsonResponse({"error": result.error or "Invalid request"}, status=result.status)

        return JsonResponse(result.payload, status=result.status)

    except Exception as e:
        # ✅ This catches unexpected crashes and prints full traceback
        print("🔥 Unexpected error in delete_market_research_entry:", str(e))
        traceback.print_exc()
        return JsonResponse({"error": "Server error"}, status=500)



# ---------------------------------------------- Save Project Location
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_POST
def save_project_location(request):
    try:
        body = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid JSON body"}, status=400)

    project_id = body.get("project_id")
    latitude = body.get("latitude")
    longitude = body.get("longitude")

    result = MarketResearchMasterDataService.save_project_location(
        project_id=project_id,
        latitude=latitude,
        longitude=longitude,
    )

    if not result.success:
        return JsonResponse({"success": False, "error": result.error or "Invalid request"}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Import Csv For Model
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@csrf_exempt
def import_csv_for_model(request):
    if request.method != "POST" or not request.FILES.get("csv_file"):
        return JsonResponse({"success": False, "error": "Invalid request"}, status=400)

    model_name = request.POST.get("model")
    csv_file = request.FILES["csv_file"]

    try:
        file_bytes = csv_file.read()
    except Exception:
        return JsonResponse({"success": False, "error": "Failed to read uploaded file"}, status=400)

    result = MarketResearchMasterDataService.import_csv_for_model(
        model_name=model_name,
        file_bytes=file_bytes,
    )

    if not result.success:
        return JsonResponse({"success": False, "error": result.error or "Import failed"}, status=result.status)

    return JsonResponse(result.payload, status=result.status)







# ---------------------------------------------- Market Unit Data List
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def market_unit_data_list(request):
    result = MarketResearchUnitsManagmentService.get_list_context(
        page=request.GET.get("page", 1),
        page_size=request.GET.get("page_size", 25),
    )

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return render(request, "ToP/market_unit_data_list.html", result.payload)


# ---------------------------------------------- Update Market Unit Field
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@csrf_exempt
@require_http_methods(["POST"])
def update_market_unit_field(request):
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    result = MarketResearchUnitsManagmentService.update_market_unit(user=request.user, data=data)

    if not result.success:
        # Return full message + trace for debugging (you can remove trace in prod)
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Create Market Unit
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@csrf_exempt
def create_market_unit(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request"}, status=400)

    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid JSON body"}, status=400)

    field = data.get("field")
    value = data.get("value")

    result = MarketResearchUnitsManagmentService.create_market_unit(user=request.user, field=field, value=value)

    if not result.success:
        return JsonResponse({"success": False, "error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Delete Market Unit
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@csrf_exempt
@require_http_methods(["POST"])
def delete_market_unit(request):
    try:
        data = json.loads(request.body or "{}")
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid JSON body"}, status=400)

    record_id = data.get("id")
    result = MarketResearchUnitsManagmentService.delete_market_unit(record_id=record_id)

    if not result.success:
        return JsonResponse({"success": False, "error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Import Market Units
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_POST
def import_market_units(request):
    if not request.FILES.get("csv_file"):
        return JsonResponse(
            {"success": False, "error": "No file provided", "error_type": "missing_file"},
            status=400
        )

    file_bytes = request.FILES["csv_file"].read()
    result = MarketResearchUnitsManagmentService.import_market_units(file_bytes=file_bytes)

    if not result.success:
        return JsonResponse(
            {"success": False, "error": result.error, "trace": result.trace, "error_type": "fatal_error"},
            status=result.status
        )

    return JsonResponse(result.payload, status=result.status)







# ---------------------------------------------- Market Research Report
def market_research_report(request):
    result = MarketResearchService.get_report_context(user=request.user)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return render(request, "ToP/market_research_report.html", result.payload)


# ---------------------------------------------- Get Market Data (Pivot API)
def get_market_data(request):
    result = MarketResearchService.get_market_data()

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Market Projects Explorer
def market_projects_explorer(request):
    result = MarketResearchService.get_projects_explorer_context(user=request.user)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return render(request, "ToP/market_research_project_detail.html", result.payload)


# ---------------------------------------------- Filter Projects
def filter_projects(request):
    result = MarketResearchService.filter_projects(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Main dashboard view
def market_dashboard(request):
    result = MarketResearchService.get_dashboard_context(user=request.user)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return render(request, "ToP/market_dashboard.html", result.payload)


# ---------------------------------------------- API endpoint for dashboard KPIs
def dashboard_kpis(request):
    result = MarketResearchService.dashboard_kpis(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- API endpoint for chart data
def dashboard_charts_data(request):
    result = MarketResearchService.dashboard_charts_data(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- API endpoint for filter options based on current selection
def dashboard_filter_data(request):
    result = MarketResearchService.dashboard_filter_data(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Export dashboard data as JSON
def dashboard_export_data(request):
    result = MarketResearchService.dashboard_export_data(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- View for the candlestick chart dashboard template
def market_candlestick_dashboard(request):
    result = MarketResearchService.get_candlestick_dashboard_context(user=request.user)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return render(request, "ToP/market_candlestick_dashboard.html", result.payload)


# ---------------------------------------------- API endpoint to provide hierarchical candlestick data for charts
def get_candlestick_data(request):
    result = MarketResearchService.get_candlestick_data(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- API endpoint to get unique values for filter dropdowns
def get_filter_options(request):
    result = MarketResearchService.get_filter_options()

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Market Charts View (hierarchical data rendered server-side)
def market_charts_view(request):
    result = MarketResearchService.get_market_charts_view_context(user=request.user, request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return render(request, "ToP/market_candlestick_dashboard.html", result.payload)






# ---------------------------------------------- Sales Performance Analysis
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "Viewer"])
def sales_performance_analysis(request):
    
    if is_company_viewer(request.user) and not viewer_can_access_page(request.user, PAGE_SALES_PERFORMANCE_ANALYSIS):
        return HttpResponseForbidden("You are not authorized to view this page.")


    result = SalesPerformanceService.get_page_context(user=request.user)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return render(request, "ToP/sales_performance_analysis.html", result.payload)


# ---------------------------------------------- Get Company Projects For Sales
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "Viewer"])
def get_company_projects_for_sales(request):
    
    if is_company_viewer(request.user) and not viewer_can_access_page(request.user, PAGE_SALES_PERFORMANCE_ANALYSIS):
        return HttpResponseForbidden("You are not authorized to view this page.")


    result = SalesPerformanceService.get_company_projects(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    # This endpoint returns a raw list (safe=False)
    return JsonResponse(result.payload, safe=False, status=result.status)


# ---------------------------------------------- Get Sales Analysis Data
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "Viewer"])
def get_sales_analysis_data(request):
    
    if is_company_viewer(request.user) and not viewer_can_access_page(request.user, PAGE_SALES_PERFORMANCE_ANALYSIS):
        return HttpResponseForbidden("You are not authorized to view this page.")


    result = SalesPerformanceService.get_sales_analysis_data(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Get Sales Analysis By Unit Model
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "Viewer"])
def get_sales_analysis_by_unit_model(request):
    
    if is_company_viewer(request.user) and not viewer_can_access_page(request.user, PAGE_SALES_PERFORMANCE_ANALYSIS):
        return HttpResponseForbidden("You are not authorized to view this page.")


    result = SalesPerformanceService.get_sales_analysis_by_unit_model(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Get Premium Analysis Data
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "Viewer"])
def get_premium_analysis_data(request):
    
    if is_company_viewer(request.user) and not viewer_can_access_page(request.user, PAGE_SALES_PERFORMANCE_ANALYSIS):
        return HttpResponseForbidden("You are not authorized to view this page.")


    result = SalesPerformanceService.get_premium_analysis_data(request=request)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)




# ---------------------------------------------- Unit Mapping (Admin)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Developer", "Uploader"])
def unit_mapping(request):
    # ✅ MUST pass user so uploader scoping works
    result = UnitMappingService.get_unit_mapping_page_context(user=request.user)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return render(request, "ToP/unit_mapping.html", result.payload)


# ---------------------------------------------- Get Project Masterplan
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Developer", "Sales", "Manager", "SalesHead", "Viewer", "Uploader"])
@viewer_page_required(PAGE_MASTERPLANS)
def get_project_masterplan(request, project_id):
    result = UnitMappingService.get_project_masterplan(user=request.user, project_id=project_id)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)



# ---------------------------------------------- Save Unit Position
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Developer", "Uploader"])
def save_unit_position(request):
    result = UnitMappingService.save_unit_position(request=request, user=request.user)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)



# ---------------------------------------------- Get Unit Details For Masterplan
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Developer", "Sales", "Manager", "SalesHead", "Viewer", "Uploader"])
@viewer_page_required(PAGE_MASTERPLANS)
def get_unit_details_for_masterplan(request, unit_code):
    result = UnitMappingService.get_unit_details_for_masterplan(user=request.user, unit_code=unit_code)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)



# ---------------------------------------------- Deletes the entire pin
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Developer", "Uploader"])
def delete_unit_position(request, position_id):
    result = UnitMappingService.delete_unit_position(request=request, position_id=position_id)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Deletes a specific unit from inside a building group
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Developer", "Uploader"])
def delete_child_unit(request, child_id):
    result = UnitMappingService.delete_child_unit(request=request, child_id=child_id)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return JsonResponse(result.payload, status=result.status)


# ---------------------------------------------- Unit Mapping Read Only (View)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "TeamMember", "Developer", "Sales", "Manager", "SalesHead", "Viewer", "Uploader"])
@viewer_page_required(PAGE_MASTERPLANS)
def unit_mapping_read_only(request):
    result = UnitMappingService.get_unit_mapping_read_only_context(user=request.user)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    return render(request, "ToP/unit_mapping_read_only.html", result.payload)


# ---------------------------------------------- Get Unit Pin Data (PDF Helper)
@login_required(login_url="login")
def get_unit_pin_data(request, unit_code):
    result = UnitMappingService.get_unit_pin_data(unit_code=unit_code)

    if not result.success:
        return JsonResponse({"error": result.error}, status=result.status)

    return JsonResponse(result.payload, status=result.status)




# ---------------------------------------------- Unit Layout Manager (HTML + AJAX)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "Uploader"])
def unit_layout_manager(request):
    result = UnitMappingService.unit_layout_manager_dispatch(request=request, user=request.user)

    if not result.success:
        return JsonResponse({"error": result.error, "trace": result.trace}, status=result.status)

    # Service returns either ("render", template, context) OR json payload
    if result.payload.get("_type") == "render":
        return render(request, result.payload["template"], result.payload["context"])

    return JsonResponse(result.payload["data"], status=result.status)


# ---------------------------------------------- Delete Unit Layout
@login_required(login_url="login")
@require_POST
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Uploader"])
def delete_unit_layout(request, layout_id):
    result = UnitMappingService.delete_unit_layout(user=request.user, layout_id=layout_id)

    if not result.success:
        return JsonResponse(
            {"success": False, "error": result.error, "trace": result.trace},
            status=result.status
        )

    return JsonResponse(result.payload, status=result.status)




# ============================== PROFESSIONAL DASHBOARD VIEWS ==============================

super_admin_service = AdminDashboardService(app_label="ToP", page_size=20)


@user_passes_test(is_superuser_check, login_url="login")
def dashboard_home(request):
    context = super_admin_service.build_home_context()
    return render(request, "ToP/admin_dashboard/dashboard_home.html", context)


@user_passes_test(is_superuser_check, login_url="login")
def dynamic_model_list(request, model_name):
    query = request.GET.get("q", "")
    page_number = request.GET.get("page")

    result = super_admin_service.list_model_objects(
        model_name=model_name,
        query=query,
        page_number=page_number,
    )

    context = {
        "model_name": result.model_name,
        "model_verbose_name": result.model_verbose_name,
        "model_verbose_name_plural": result.model_verbose_name_plural,
        "objects": result.page_obj,
        "fields": result.fields,
        "page_obj": result.page_obj,
        "is_paginated": result.page_obj.has_other_pages(),
        "query": result.query,
        "all_models": result.all_models,
        "can_create": result.can_create,
    }
    return render(request, "ToP/admin_dashboard/model_list.html", context)


@user_passes_test(is_superuser_check, login_url="login")
def dynamic_model_create(request, model_name):
    if request.method == "POST":
        outcome = super_admin_service.create_instance(
            model_name=model_name,
            post_data=request.POST,
            files=request.FILES,
        )

        # Preserved behavior: block if can_create False
        if outcome.get("blocked"):
            messages.error(request, "Creation is disabled for this model.")
            return redirect("dynamic_model_list", model_name=model_name)

        if outcome["ok"]:
            config = outcome["config"]
            messages.success(request, f"{config.model._meta.verbose_name} created successfully.")
            return redirect("dynamic_model_list", model_name=model_name)

        # invalid form -> render with errors
        config = outcome["config"]
        context = {
            "form": outcome["form"],
            "model_name": model_name,
            "model_verbose_name": config.model._meta.verbose_name,
            "action": "Create",
            "all_models": super_admin_service.list_model_objects(model_name=model_name, query="", page_number=None).all_models,
        }
        return render(request, "ToP/admin_dashboard/model_form.html", context)

    # GET
    result = super_admin_service.get_create_form(model_name=model_name)
    context = {
        "form": result.form,
        "model_name": result.model_name,
        "model_verbose_name": result.model_verbose_name,
        "action": result.action,
        "all_models": result.all_models,
    }
    return render(request, "ToP/admin_dashboard/model_form.html", context)


@user_passes_test(is_superuser_check, login_url="login")
def dynamic_model_update(request, model_name, pk):
    if request.method == "POST":
        outcome = super_admin_service.update_instance(
            model_name=model_name,
            pk=pk,
            post_data=request.POST,
            files=request.FILES,
        )

        config = outcome["config"]

        if outcome["ok"]:
            messages.success(request, f"{config.model._meta.verbose_name} updated successfully.")
            return redirect("dynamic_model_list", model_name=model_name)

        # invalid form -> render with errors
        context = {
            "form": outcome["form"],
            "model_name": model_name,
            "model_verbose_name": config.model._meta.verbose_name,
            "action": "Update",
            "all_models": super_admin_service.list_model_objects(model_name=model_name, query="", page_number=None).all_models,
        }
        return render(request, "ToP/admin_dashboard/model_form.html", context)

    # GET
    result = super_admin_service.get_update_form(model_name=model_name, pk=pk)
    context = {
        "form": result.form,
        "model_name": result.model_name,
        "model_verbose_name": result.model_verbose_name,
        "action": result.action,
        "all_models": result.all_models,
    }
    return render(request, "ToP/admin_dashboard/model_form.html", context)


@user_passes_test(is_superuser_check, login_url="login")
def dynamic_model_delete(request, model_name, pk):
    # Preserve "deletion disabled" behavior
    if not super_admin_service.can_delete(model_name=model_name):
        messages.error(request, "Deletion is disabled for this model.")
        return redirect("dynamic_model_list", model_name=model_name)

    if request.method == "POST":
        deleted_obj = super_admin_service.delete_instance(model_name=model_name, pk=pk)
        messages.success(request, f"{deleted_obj._meta.verbose_name} deleted successfully.")
        return redirect("dynamic_model_list", model_name=model_name)

    # GET confirm
    result = super_admin_service.get_delete_context(model_name=model_name, pk=pk)
    context = {
        "object": result.obj,
        "model_name": result.model_name,
        "model_verbose_name": result.model_verbose_name,
        "all_models": result.all_models,
    }
    return render(request, "ToP/admin_dashboard/model_confirm_delete.html", context)



# --- Capture View ---
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@ensure_csrf_cookie
def attendance_capture_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if not all([data.get('action'), data.get('latitude'), data.get('longitude'), data.get('image')]):
                raise ValueError("Missing required fields.")

            AttendanceActionService.record_attendance(
                user=request.user,
                action=data.get('action'),
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                image_b64=data.get('image')
            )
            return JsonResponse({'status': 'success', 'message': 'Attendance recorded.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return render(request, 'attendance/capture.html')

# --- Management Dashboard ---
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer"])
def management_dashboard_view(request):
    
    # 1. Get ALL Data (No filtering on backend)
    all_records = AttendanceQueryService.get_all_grouped_data()

    # 2. Serialize to JSON string for the frontend
    # Use Django's safe filter in template, but here we prep the list
    
    context = {
        # Convert list of dicts to JSON string
        'attendance_data_json': json.dumps(all_records), 
    }
    return render(request, 'attendance/dashboard.html', context)

# --- Delete Log ---
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer"])
def delete_attendance_log(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            AttendanceActionService.delete_logs(data.get('ids', []))
            return JsonResponse({'status': 'success', 'message': 'Records deleted.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer"])
def cleanup_images_view(request):
    if request.method == 'POST' and request.user.role in ["Admin", "Developer"]:
        try:
            # Trigger Service
            count = AttendanceActionService.cleanup_old_images(days=30)
            return JsonResponse({'status': 'success', 'message': f'Cleanup Complete. {count} images deleted.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Unauthorized or Invalid Method'}, status=403)






# ----------------------------------------------
# Pricing Model
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def pricing_model(request):
    context = PricingService.pricing_model_context(user=request.user)
    return render(request, "ToP/pricing_model.html", context)


# ----------------------------------------------
# Projects by company
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def get_company_projects(request):
    payload = PricingService.get_company_projects_payload(request.GET.get("company_id"))
    return JsonResponse(payload)


# ----------------------------------------------
# Project units + criteria merged
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def get_project_units_simple(request):
    payload = PricingService.get_project_units_with_criteria_payload(request.GET.get("project_id"))
    return JsonResponse(payload)


# ----------------------------------------------
# Save pricing criteria (single field)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def save_pricing_criteria_view(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid request method."})

    try:
        payload = PricingService.save_pricing_criteria(
            project_id=request.POST.get("project_id"),
            unit_model=request.POST.get("unit_model"),
            field_name=request.POST.get("field_name"),
            field_value_raw=request.POST.get("field_value"),
        )
        return JsonResponse(payload)
    except Exception:
        # Same behavior: generic error
        return JsonResponse({"success": False, "error": "An error occurred while saving the criteria."})


# ----------------------------------------------
# Premium groups
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def get_premium_groups(request):
    payload = PricingService.get_premium_groups_payload(request.GET.get("project_id"))
    return JsonResponse(payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_http_methods(["POST"])
def add_premium_group(request):
    payload = PricingService.add_premium_group(
        project_id=request.POST.get("project_id"),
        name=request.POST.get("name", ""),
    )
    return JsonResponse(payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_http_methods(["POST"])
def delete_premium_group(request):
    payload = PricingService.delete_premium_group(group_id=request.POST.get("group_id"))
    return JsonResponse(payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_http_methods(["POST"])
def add_premium_subgroup(request):
    payload = PricingService.add_premium_subgroup(
        group_id=request.POST.get("group_id"),
        name=request.POST.get("name", ""),
        value_str=request.POST.get("value", ""),
    )
    return JsonResponse(payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_http_methods(["POST"])
def delete_premium_subgroup(request):
    payload = PricingService.delete_premium_subgroup(subgroup_id=request.POST.get("subgroup_id"))
    return JsonResponse(payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def get_project_premium_groups(request):
    payload = PricingService.get_project_premium_group_names_payload(request.GET.get("project_id"))
    return JsonResponse(payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
def get_project_subgroups_data(request):
    payload = PricingService.get_project_subgroups_data_payload(request.GET.get("project_id"))
    return JsonResponse(payload)


# ----------------------------------------------
# Save unit premium selection (group -> Unit field mapping)
@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_http_methods(["POST"])
def save_unit_premium_view(request):
    payload = PricingService.save_unit_premium_selection(
        unit_code=request.POST.get("unit_code"),
        group_name=request.POST.get("group_name"),
        selected_subgroup_name=request.POST.get("selected_subgroup_name", ""),
    )
    return JsonResponse(payload)


# ----------------------------------------------
# Save calculated fields on unit
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@login_required(login_url="login")
@require_http_methods(["POST"])
def save_unit_base_price(request):
    payload = PricingService.save_unit_base_price(
        unit_code=request.POST.get("unit_code"),
        base_price_raw=request.POST.get("base_price"),
    )
    return JsonResponse(payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_http_methods(["POST"])
def save_unit_base_psm(request):
    payload = PricingService.save_unit_base_psm(
        unit_code=request.POST.get("unit_code"),
        base_psm_raw=request.POST.get("base_psm"),
    )
    return JsonResponse(payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember"])
@require_http_methods(["POST"])
def save_unit_premium_totals(request):
    payload = PricingService.save_unit_premium_totals(
        unit_code=request.POST.get("unit_code"),
        total_premium_percent_raw=request.POST.get("total_premium_percent"),
        total_premium_value_raw=request.POST.get("total_premium_value"),
    )
    return JsonResponse(payload)






@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember","Manager", "Sales", "SalesHead"])
def historical_sales_requests_analysis_page(request):
    result = HistoricalSalesRequestsAnalysisService.build_page_context(user=request.user)
    if not result.success:
        return render(request, "ToP/historical_sales_requests_analysis.html", status=result.status)

    payload = result.payload or {}

    return render(
        request,
        "ToP/historical_sales_requests_analysis.html",
        {
            "scope_role": payload.get("scope_role"),
            "companies": payload.get("companies"),
            "company": payload.get("company"),
            "preselected_company": payload.get("preselected_company"),
        },
    )


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember","Manager", "Sales", "SalesHead"])
def historical_sales_requests_analysis_data(request):
    company_id = request.GET.get("company_id")
    try:
        company_id_int = int(company_id) if company_id else None
    except ValueError:
        company_id_int = None

    result = HistoricalSalesRequestsAnalysisService.get_approved_rows(
        user=request.user,
        company_id=company_id_int,
    )

    if not result.success:
        return JsonResponse({"success": False, "error": result.error or "Error"}, status=result.status)

    return JsonResponse(result.payload, status=200)



from .services.sales_team_report_service import SalesTeamReportService


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "SalesHead"])
def sales_team_report(request):
    res = SalesTeamReportService.build_page_context(user=request.user)
    if not res.ok:
        return JsonResponse({"success": False, "error": res.error}, status=res.status)

    return render(request, "ToP/sales_team_report.html", res.payload)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "SalesHead"])
def ajax_sales_teams(request):
    company_id = request.GET.get("company_id")
    try:
        company_id = int(company_id) if company_id else None
    except Exception:
        company_id = None

    res = SalesTeamReportService.list_teams_for_user(user=request.user, company_id=company_id)
    if not res.ok:
        return JsonResponse({"success": False, "error": res.error}, status=res.status)

    return JsonResponse({"success": True, **(res.payload or {})}, status=res.status)


@login_required(login_url="login")
@allowed_users(allowed_roles=["Admin", "Developer", "TeamMember", "Manager", "SalesHead"])
def ajax_sales_team_report(request):
    team_id = request.GET.get("team_id")
    try:
        team_id = int(team_id)
    except Exception:
        return JsonResponse({"success": False, "error": "team_id is required"}, status=400)

    res = SalesTeamReportService.build_team_report(user=request.user, team_id=team_id)
    if not res.ok:
        return JsonResponse({"success": False, "error": res.error}, status=res.status)

    return JsonResponse({"success": True, **(res.payload or {})}, status=res.status)
