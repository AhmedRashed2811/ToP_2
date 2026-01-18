from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.utils.timezone import now

from ..models import (
    Company,
    Project,
    Unit,
    Sales,
    SalesHead,
    Manager,
    SalesRequest,
    ProjectConfiguration,
    ProjectExtendedPayments,
    ProjectExtendedPaymentsSpecialOffer,
    ProjectWebConfiguration,
    Constraints,
    BaseNPV,
)

from ..utils.viewer_permissions import is_company_viewer, viewer_company, viewer_allowed_statuses
from ..utils.viewer_permissions import is_company_viewer, viewer_allowed_statuses


# -----------------------------
# Scope result container
# -----------------------------
@dataclass
class UserScope:
    user_company: Optional[Any]
    is_client_user: bool
    user_role: Optional[str]
    context_updates: Dict[str, Any]


# -----------------------------
# Initial context builder
# -----------------------------
def init_home_context(*, session) -> Dict[str, Any]:
    return {
        "today": now(),
        # We now allow ALL companies since they all use the Native strategy
        "companies": Company.objects.all(),
        "projects": Project.objects.all(),
        "project_data": list(Project.objects.values("name", "company__name")),
        "units": Unit.objects.none(), # Default empty
        "units_json": "[]",
        "unit": None,
        "clients": "{}",
        "base_dp": 0,
        "half_base_dp": 0,
        "total_uncovered_area": 0,
        "unit_query": "",
        "project_query": "",
        "is_impersonating": session.get("impersonator_id") is not None,
        "is_company_active": None,
        "is_not_native_company": False, # Always false now -> Uses standard UI
        "user_can_edit": True,
        "user_can_change_years": True,
        "special_offers": None,
        "tenor_range": None,
        "project_config": None,
        "project_web_config": None,
        "project_constraints": None,
        "base_npv": None,
        "user_company": None,
        "company": None,
    }


# -----------------------------
# Determine user scope
# -----------------------------
def resolve_user_scope(*, user, session) -> UserScope:
    user_company = None
    is_client_user = False
    is_sales_user = user.groups.filter(name__in=["Client", "Sales"]).exists()
    is_sales_head_user = user.groups.filter(name__in=["SalesHead"]).exists()
    role = getattr(user, "role", None)
    
    is_viewer_user = is_company_viewer(user)

    context_updates: Dict[str, Any] = {}

    # 1. Handle Admin / Developer / TeamMember (Global Access)
    if user.is_superuser or user.groups.filter(name__in=["Admin", "Developer", "TeamMember"]).exists():
        return UserScope(
            user_company=None,
            is_client_user=False,
            user_role="Admin",
            context_updates={
                "is_company_active": None, # Skip the active/inactive check in template
                "user_can_edit": True,
                "user_can_change_years": True
            }
        )

    # 2. Handle Regular Company Users
    
    if is_viewer_user:
        user_company = viewer_company(user)
        context_updates["user_can_edit"] = True
        context_updates["user_can_change_years"] = True
        context_updates["is_company_active"] = user_company.is_active if user_company else False
        context_updates["company"] = user_company
        is_client_user = True  # treat as sales member
        return UserScope(
            user_company=user_company,
            is_client_user=is_client_user,
            user_role="Viewer",
            context_updates=context_updates,
        )



    try:
        if is_sales_user:
            company_user = Sales.objects.get(user=user)
            user_company = company_user.company
            context_updates["user_can_edit"] = company_user.can_edit
            context_updates["user_can_change_years"] = company_user.can_change_years
            context_updates["is_company_active"] = user_company.is_active
            context_updates["company"] = user_company
            
        elif is_sales_head_user:
            company_user = SalesHead.objects.get(user=user)
            user_company = company_user.company
            context_updates["user_can_edit"] = True
            context_updates["user_can_change_years"] = True
            context_updates["is_company_active"] = user_company.is_active
            context_updates["company"] = user_company
            
            
        elif user.groups.filter(name="Manager").exists():
            company_manager = Manager.objects.get(user=user)
            user_company = company_manager.company
            context_updates["is_company_active"] = user_company.is_active
            context_updates["company"] = user_company
            


    except (Sales.DoesNotExist, SalesHead.DoesNotExist ,Manager.DoesNotExist):
        context_updates["is_company_active"] = False
        
    if is_sales_user or  is_sales_head_user:
        is_client_user = True

    return UserScope(
        user_company=user_company,
        is_client_user=is_client_user,
        user_role=role,
        context_updates=context_updates,
    )

# -----------------------------
# Project map for manual resolution
# -----------------------------
def build_project_map(projects_qs) -> Dict[int, str]:
    return {p.id: p.name for p in projects_qs}


# -----------------------------
# Serialize units for JS (Cleaned up for Native Only)
# -----------------------------
def serialize_units_for_js(*, units_obj, project_map: Dict[int, str]) -> str:
    try:
        serialized_units = []
        if units_obj:
            for u in units_obj:
                # Handle project name resolution based on model field type (FK or Char)
                p_val = getattr(u, "project", None)
                p_name = ""
                
                # If project is a string (Char field)
                if isinstance(p_val, str):
                    p_name = p_val
                # If project is an ID/Int (ForeignKey)
                elif isinstance(p_val, int):
                    p_name = project_map.get(p_val, "")
                # If project is a Model Object
                elif hasattr(p_val, 'name'):
                    p_name = p_val.name

                serialized_units.append({
                    "unit_code": u.unit_code,
                    "status": u.status,
                    "price": float(u.interest_free_unit_price) if u.interest_free_unit_price else 0,
                    "project_name": p_name,
                })

        return json.dumps(serialized_units)

    except Exception:
        return "[]"


# -----------------------------
# Area helper
# -----------------------------
def compute_total_uncovered_area(unit_obj) -> float:
    u_terr = float(getattr(unit_obj, "uncovered_terraces", 0) or 0)
    r_terr = float(getattr(unit_obj, "roof_terraces_area", 0) or 0)
    return u_terr + r_terr


# -----------------------------
# Enforce client logic
# -----------------------------
def enforce_client_unit_rules_and_limits(
    *,
    user,
    is_client_user: bool,
    user_company,
    found_unit,
    messages_api=None,
    request_for_messages=None,
):
    result = {"redirect_home": False, "found_unit": found_unit}

    if not found_unit:
        return result


    # --- Case B: Client User (Sales) Logic ---
    if is_client_user:
        current_count = SalesRequest.objects.filter(sales_man=user).count()

        p_val = getattr(found_unit, "project", None)
        p_name = str(p_val) if p_val else ""

        target_project = Project.objects.filter(name=p_name, company=user_company).first()
        if target_project:
            p_config = ProjectConfiguration.objects.filter(project=target_project).first()
            if p_config:
                limit = p_config.maximum_requests_per_sales
                if current_count >= limit:
                    if messages_api and request_for_messages:
                        messages_api.error(request_for_messages, "You have exceeded your maximum allowed requests.")
                    return {"redirect_home": True, "found_unit": None}


        status = getattr(found_unit, "status", "Available")

        if is_company_viewer(user):
            allowed_statuses = viewer_allowed_statuses(user)
            if not allowed_statuses or status not in allowed_statuses:
                return {"redirect_home": True, "found_unit": None}
        else:
            if status != "Available":
                return {"redirect_home": True, "found_unit": None}
            

    return result


# -----------------------------
# Project search and load configuration
# -----------------------------
def handle_project_search_and_load_config(*, project_query: str, context: Dict[str, Any], user_can_change_years: bool) -> None:
    context["project_query"] = project_query

    if project_query:
        project = Project.objects.filter(name__icontains=project_query).first()
        if project:
            load_project_configuration(
                context=context,
                project=project,
                user_can_change_years=user_can_change_years,
            )


def _clean_allowed_years(raw_list) -> list[int]:
    if not raw_list:
        return []
    out = []
    seen = set()
    for x in raw_list:
        try:
            n = int(x)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 12 and n not in seen:
            seen.add(n)
            out.append(n)
    return sorted(out)


def load_project_configuration(*, context: Dict[str, Any], project, user_can_change_years: bool) -> None:
    context["project"] = project

    config = ProjectConfiguration.objects.filter(project=project).first()
    context["project_config"] = config

    web_config = ProjectWebConfiguration.objects.filter(project=project).first()
    context["project_web_config"] = web_config

    if config:
        scheme = config.default_scheme.replace(" ", "").lower()
        if scheme == "flatbackloaded":
            scheme = "flat_back_loaded"
        elif scheme == "bulletbackloaded":
            scheme = "bullet_back_loaded"
        elif scheme == "flat":
            scheme = "flat"
        elif scheme == "bullet":
            scheme = "bullet"
        else:
            scheme = config.default_scheme.lower()

        plan = ProjectExtendedPayments.objects.filter(
            project=project,
            year=config.base_tenor_years,
            scheme=scheme,
        ).first()

        if plan:
            base_dp = (plan.dp1 + plan.dp2) * 100
            context["base_dp"] = base_dp
            context["half_base_dp"] = base_dp / 2
        else:
            context["base_dp"] = 0
            context["half_base_dp"] = 0

        # ---- TENOR RANGE logic ----
        if user_can_change_years is False:
            allowed = _clean_allowed_years(getattr(web_config, "allowed_years_for_sales", []) if web_config else [])
            context["tenor_range"] = allowed 
        else:
            context["tenor_range"] = range(1, config.max_tenor_years + 1)

    else:
        context["tenor_range"] = None
        context["base_dp"] = 0
        context["half_base_dp"] = 0

    context["project_constraints"] = Constraints.objects.filter(project_config=config).first()
    context["base_npv"] = BaseNPV.objects.filter(project_config=config).first()
    context["special_offers"] = ProjectExtendedPaymentsSpecialOffer.objects.filter(project=project)


# -----------------------------
# Post-load request limits check
# -----------------------------
def check_request_limits_after_project_load(
    *,
    user,
    context: Dict[str, Any],
    messages_api=None,
    request_for_messages=None,
) -> Dict[str, Any]:
    try:
        if context.get("project_config"):
            limit = context["project_config"].maximum_requests_per_sales
            current_count = SalesRequest.objects.filter(sales_man=user).count()
            if current_count >= limit:
                if messages_api and request_for_messages:
                    messages_api.error(request_for_messages, "You Exceeded Requests")
                return {"redirect_home": True}
    except Exception:
        pass

    return {"redirect_home": False}