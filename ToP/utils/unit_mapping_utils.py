# ToP/utils/unit_mapping_utils.py

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

from ..models import (
    Company,
    Manager,
    Sales,
    Project,
    Unit,
    UnitLayout,
    SalesHead
)


# ----------------------------------------------
# Serialize local Unit (Unified Schema)
# ----------------------------------------------
def serialize_unit(unit: Unit) -> Dict[str, Any]:
    """
    Serializes a Unit object for the frontend.
    Determines lock status strictly based on the 'status' field.
    """
    raw_status = str(unit.status or "Available").strip()
    is_available = raw_status.lower() == "available"
    
    return {
        "unit_code": unit.unit_code,
        "num_bedrooms": unit.num_bedrooms or "-",
        "status": raw_status,
        "is_locked": not is_available,  # Locked if not 'Available'
        "gross_area": str(unit.gross_area) if unit.gross_area else "-",
        "interest_free_unit_price": str(unit.interest_free_unit_price) if unit.interest_free_unit_price else "-",
        "development_delivery_date": unit.development_delivery_date.strftime("%Y-%m-%d") if unit.development_delivery_date else "-",
        "finishing_specs": unit.finishing_specs or "-",
        "garden_area": str(unit.garden_area) if unit.garden_area else "-",
        "land_area": str(unit.land_area) if unit.land_area else "-",
        "penthouse_area": str(unit.penthouse_area) if unit.penthouse_area else "-",
        "roof_terraces_area": str(unit.roof_terraces_area) if unit.roof_terraces_area else "-",
        "floor": unit.floor or "-",
        
        # Layout lookup keys
        "building_type": unit.building_type,
        "unit_type": unit.unit_type,
        "unit_model": unit.unit_model,
    }


# ----------------------------------------------
# Role flags + visibility rules
# ----------------------------------------------
from .viewer_permissions import is_company_viewer  # adjust import path if needed

def get_role_flags_for_masterplan(user) -> Tuple[bool, bool]:
    # Treat viewer as "client-ish" (read-only restriction)
    is_client = user.groups.filter(name__in=["Sales", "SalesHead"]).exists() or is_company_viewer(user)
    is_managerish = user.groups.filter(name__in=["Manager", "Admin", "Developer", "TeamMember"]).exists()
    return is_client, is_managerish


def should_filter_available_only(*, is_client: bool, is_managerish: bool, show_all_flag: bool) -> bool:
    return bool(is_client and (not is_managerish) and (not show_all_flag))


def compute_display_status_for_client(*, is_client: bool, is_managerish: bool, raw_status: str, is_locked: bool) -> str:
    if is_client and (not is_managerish) and is_locked:
        return "Blocked Development"
    return raw_status


# ----------------------------------------------
# Build masterplan unit data map (DB ONLY)
# ----------------------------------------------
def build_masterplan_unit_data_map(*, project: Project) -> Dict[str, Dict[str, Any]]:
    """
    Fetches all units for the project from the Local DB (Warehouse).
    Map Key: unit_code
    """
    unit_data_map: Dict[str, Dict[str, Any]] = {}

    # Query local DB (Project link via project_company or name match)
    # Using project_company is safer if your import hub sets it
    db_units = Unit.objects.filter(project=project.name, company=project.company).values(
        "unit_code",
        "status",
        "num_bedrooms",
        "finishing_specs",
        "gross_area",
        "unit_model",
    )
    
    for u in db_units:
        raw_status = str(u["status"] or "Available").strip()
        is_locked = raw_status.lower() != "available"

        unit_data_map[u["unit_code"]] = {
            "unit_code": u["unit_code"],
            "status": raw_status,
            "is_locked": is_locked,
            "bedrooms": str(u["num_bedrooms"]) if u["num_bedrooms"] is not None else "-",
            "finishing": u["finishing_specs"] or "N/A",
            "area": float(u["gross_area"] or 0),
            "model": u["unit_model"] or "N/A",
        }

    return unit_data_map


# ----------------------------------------------
# Floor sorting + local unit finder
# ----------------------------------------------
def get_floor_sort_index(floor_val: Any) -> int:
    if not floor_val:
        return 999
    fv = str(floor_val).upper().strip()
    if fv in ["LG", "LOWER", "BASEMENT"]:
        return -1
    if fv in ["G", "GROUND"]:
        return 0
    # Try to extract number
    import re
    nums = re.findall(r'-?\d+', fv)
    if nums:
        return int(nums[0])
    return 999


def find_local_unit(code: str) -> Optional[Unit]:
    # 1. Exact Match
    unit = Unit.objects.filter(unit_code=code).first()
    if unit:
        return unit

    # 2. Case Insensitive
    unit = Unit.objects.filter(unit_code__iexact=code).first()
    if unit: 
        return unit

    # 3. Suffix Stripping (e.g. U101_CompName -> U101)
    if "_" in code:
        base_code = code.split("_")[0]
        unit = Unit.objects.filter(unit_code=base_code).first()
        if unit:
            return unit

    return None


# ----------------------------------------------
# Layout images lookup
# ----------------------------------------------
def get_layout_images(*, project: Project, b_type: Any, u_type: Any, u_model: Any) -> List[str]:
    if not (b_type and u_type and u_model):
        return []

    layouts = UnitLayout.objects.filter(
        project=project,
        building_type=b_type,
        unit_type=u_type,
        unit_model=u_model,
    ).order_by("-created_at")

    return [l.image.url for l in layouts]


# ----------------------------------------------
# Layout manager helpers
# ----------------------------------------------
def is_ajax(request) -> bool:
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def is_restricted_layout_user(user) -> bool:
    return user.groups.filter(name="Manager").exists() or user.groups.filter(name="Client").exists()


def build_layout_manager_context(*, user) -> Dict[str, Any]:
    
    is_manager = user.groups.filter(name="Manager").exists()
    is_sales = user.groups.filter(name="Sales").exists()
    is_saleshead = user.groups.filter(name="SalesHead").exists()
    is_sales_or_head = is_sales or is_saleshead

    user_company = None

    companies: List[Any] = []
    sel_company_id = None
    is_restricted_user = False

    if is_manager:
        manager_profile = Manager.objects.filter(user=user).select_related("company").first()
        if manager_profile and manager_profile.company:
            sel_company_id = manager_profile.company.id
            user_company = manager_profile.company
            companies = [manager_profile.company]
            is_restricted_user = True

    elif is_sales_or_head:
        # ✅ SalesHead has priority if user has both groups
        client_profile = None

        if is_saleshead:
            client_profile = SalesHead.objects.filter(user=user).select_related("company").first()

        if not client_profile and is_sales:
            client_profile = Sales.objects.filter(user=user).select_related("company").first()

        if client_profile and client_profile.company:
            sel_company_id = client_profile.company.id
            user_company = client_profile.company
            companies = [client_profile.company]
            is_restricted_user = True


    else:
        # Admin / Team / Developer
        companies = list(Company.objects.filter(is_active=True).values("id", "name"))

    return {
        "is_manager": is_restricted_user,
        "companies": list(companies),
        "initial_company_id": sel_company_id,
        "company": user_company,
    }


def extract_layout_filters(request) -> Dict[str, Any]:
    return {
        "company": request.GET.get("company"),
        "project": request.GET.get("project"),
        "building_type": request.GET.get("building_type"),
        "unit_type": request.GET.get("unit_type"),
        "unit_model": request.GET.get("unit_model"),
    }


# ----------------------------------------------
# Native dropdowns (Source of Truth)
# ----------------------------------------------
def native_dropdown_values(*, p_id: Any, b_type: Any, u_type: Any, u_model: Any) -> Tuple[List[str], List[str], List[str]]:
    building_types: List[str] = []
    unit_types: List[str] = []
    unit_models: List[str] = []

    # Filter units by project (using project name/company match or FK)
    # Assuming Unit has FK 'project_company' or we filter by name
    if not p_id:
        return [], [], []
    
    project = Project.objects.filter(id=p_id).first()
    if not project:
        return [], [], []

    # Base QS for this project
    qs = Unit.objects.filter(project=project.name, company=project.company)

    if not b_type:
        building_types = list(qs.values_list("building_type", flat=True).distinct().order_by("building_type"))
        # Filter out None/Empty
        building_types = [x for x in building_types if x]

    if b_type and not u_type:
        qs = qs.filter(building_type=b_type)
        unit_types = list(qs.values_list("unit_type", flat=True).distinct().order_by("unit_type"))
        unit_types = [x for x in unit_types if x]

    if b_type and u_type and not u_model:
        qs = qs.filter(building_type=b_type, unit_type=u_type)
        unit_models = list(qs.values_list("unit_model", flat=True).distinct().order_by("unit_model"))
        unit_models = [x for x in unit_models if x]

    return building_types, unit_types, unit_models


def unique_gallery_from_layouts(layouts_qs) -> List[Dict[str, Any]]:
    seen_urls = set()
    gallery_data: List[Dict[str, Any]] = []

    for l in layouts_qs:
        if not l.image: continue
        url = l.image.url
        if url in seen_urls:
            continue
        gallery_data.append({"id": l.id, "url": url, "label": l.unit_model})
        seen_urls.add(url)

    return gallery_data