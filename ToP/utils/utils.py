# -----------------------------
# Helpers (Uploader Scoping)
# -----------------------------
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from ToP.models import Company, Project
import json

from ToP.services.erp_hold_post_mapping_service import ERPHoldPostMappingService
from ToP.services.erp_leads_mapping_service import ERPLeadsMappingService
from ToP.services.erp_unit_mapping_service import ERPUnitMappingService

def _get_uploader_company(user):
    uploader_profile = getattr(user, "uploader_profile", None)
    if uploader_profile and getattr(uploader_profile, "company_id", None):
        return uploader_profile.company
    return None

def _projects_qs_for_user(user):
    uploader_company = _get_uploader_company(user)
    if uploader_company:
        return Project.objects.filter(company=uploader_company)
    return Project.objects.all()


def _get_locked_company_for_uploader(user):
    """
    If user is an Uploader and has uploader_profile -> return its company, else None.
    """
    try:
        return user.uploader_profile.company
    except Exception:
        return None
    
    
def _read_confirm_text(request) -> str:
    """
    Reads confirm_text from JSON body OR form-data.
    """
    # JSON body
    try:
        data = json.loads(request.body or "{}")
        if isinstance(data, dict):
            return (data.get("confirm_text") or "").strip()
    except Exception:
        pass

    # Form-data / POST
    return (request.POST.get("confirm_text") or "").strip()



def _distinct_clean(qs, field):
    """
    Return sorted distinct non-empty values for a CharField/TextField.
    """
    values = (
        qs.exclude(**{f"{field}__isnull": True})
          .exclude(**{f"{field}__exact": ""})
          .values_list(field, flat=True)
          .distinct()
    )
    # sort in python to avoid DB collation issues
    return sorted(set([v.strip() for v in values if str(v).strip()]))



def _resolve_user_company(user):
    """
    Resolve company from your role profile models:
    SalesHead, Sales, SalesOperation, CompanyViewer, Manager, Uploader, CompanyAdmin.
    Returns Company or None.
    """
    
    profile_attrs = [
        "sales_head_profile",
        "sales_profile",
        "sales_ops_profile",
        "viewer_profile",
        "manager_profile",
        "uploader_profile",
        "company_admin_profile",
    ]

    for attr in profile_attrs:
        prof = getattr(user, attr, None)
        if prof and getattr(prof, "company", None):
            return prof.company

    return None


def _is_admin(user):
    return user.groups.filter(name="Admin").exists()




def _mapping_page(request, *, mode: str):
    """
    mode: "unit" or "leads" or "hold_post"
    Uses same template: ToP/erp_mapping_manager.html
    """
    company_id = request.GET.get("company_id")

    body_data = None
    if request.method == "POST":
        try:
            body_data = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return JsonResponse({"success": False, "error": "Invalid JSON body"}, status=400)

        if not company_id:
            company_id = body_data.get("company_id")

    company = get_object_or_404(Company, id=company_id) if company_id else None

    # ----------------------------
    # POST: save mappings
    # ----------------------------
    if request.method == "POST":
        if not company:
            return JsonResponse({"success": False, "error": "company_id is required"}, status=400)

        mappings = (body_data or {}).get("mappings", [])

        if mode == "unit":
            result = ERPUnitMappingService.save_mappings(company=company, mappings=mappings)
            return JsonResponse(result.payload, status=result.status)

        if mode == "leads":
            result = ERPLeadsMappingService.save_mappings(company=company, mappings=mappings)
            return JsonResponse(result.payload, status=result.status)

        # mode == "hold_post"
        result = ERPHoldPostMappingService.save_mappings(company=company, mappings=mappings)
        return JsonResponse(result.payload, status=result.status)

    # ----------------------------
    # GET: render page
    # ----------------------------
    companies = Company.objects.all().order_by("name")

    if mode == "unit":
        existing = ERPUnitMappingService.get_mapping_dict(company=company) if company else {}
        target_fields = ERPUnitMappingService.get_unit_field_names()
        subtitle = "Map external ERP/API field names to your Unit model fields."
        example_left = "price"
        example_right = "interest_free_unit_price"
        needed_label = "Needed Name (Unit field)"
    elif mode == "leads":
        existing = ERPLeadsMappingService.get_mapping_dict(company=company) if company else {}
        target_fields = ERPLeadsMappingService.get_common_leads_keys()
        subtitle = "Map external Leads API field names to your internal Leads keys."
        example_left = "clientMobile"
        example_right = "phone"
        needed_label = "Needed Name (Leads key)"
    else:
        existing = ERPHoldPostMappingService.get_mapping_dict(company=company) if company else {}
        target_fields = ERPHoldPostMappingService.get_common_hold_post_keys()
        subtitle = "Map ERP HOLD/BLOCK POST payload keys to your internal keys (used in code)."
        example_left = "ced_name"
        example_right = "unit_code"
        needed_label = "Needed Name (Internal key)"

    context = {
        "mapping_mode": mode,  # "unit" | "leads" | "hold_post"
        "companies": companies,
        "selected_company": company,
        "existing_mappings_json": json.dumps(existing),
        "target_fields": target_fields,
        "subtitle": subtitle,
        "example_left": example_left,
        "example_right": example_right,
        "needed_label": needed_label,
    }
    return render(request, "ToP/erp_mapping_manager.html", context)

