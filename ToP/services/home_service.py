# ToP/services/home_inventory_service.py

from __future__ import annotations

import json
from typing import Any, Dict

from ..models import Project, Unit

from ..strategies.inventory_strategy import get_inventory_strategy

from ..utils.home_utils import (
    init_home_context,
    resolve_user_scope,
    build_project_map,
    serialize_units_for_js,
    compute_total_uncovered_area,
    handle_project_search_and_load_config,
    check_request_limits_after_project_load,
    enforce_client_unit_rules_and_limits,
)

from ..utils.viewer_permissions import is_company_viewer, viewer_allowed_statuses



class TOPHomeService:
    """
    - Service gets primitives only (no HttpRequest).
    - Preserves logic and context keys.
    """

    @staticmethod
    def build_home_response(
        *,
        user,
        session,
        method: str,
        unit_query: str,
        project_query: str,
        # Optional (if you later want to preserve messages exactly)
        messages_api=None,
        request_for_messages=None,
    ) -> Dict[str, Any]:
        # 1) Initial context (same keys)
        context = init_home_context(session=session)

        # 2) Determine user scope (Sales / Manager / else)
        scope = resolve_user_scope(user=user, session=session)
        context.update(scope.context_updates)

        user_company = scope.user_company
        is_client_user = scope.is_client_user
        

        # --- NEW: Pass is_client_user to context for Template Logic ---
        context["is_client_user"] = is_client_user 
        
        # Ensure booleans exist
        user_can_edit = context.get("user_can_edit", False)
        user_can_change_years = context.get("user_can_change_years", False)
        
        
        context["user_can_edit"] = user_can_edit
        context["user_can_change_years"] = user_can_change_years

        context["is_restricted_sales_user"] = (
            is_client_user and not user_can_edit and not user_can_change_years
        )
        
        
        # Put queries into context (preserve)
        context["unit_query"] = unit_query or ""
        context["selected_unit_code"] = unit_query or ""
        context["project_query"] = project_query or ""

        # 3) Inventory strategy path 
        if user_company and context.get("is_company_active"):
            context["user_company"] = user_company
            context["company"] = user_company
            context["is_not_native_company"] = False # Always Native now

            # Fetch projects for user company
            projects = Project.objects.filter(company=user_company)
            context["projects"] = projects

            # For manual project name resolution in JS serialization
            project_map = build_project_map(projects)

            strategy = get_inventory_strategy(user_company)

            # A) units - UPDATED to pass exclude_blocked
            # Viewer: do NOT force Available-only, use JSON statuses instead
            if is_company_viewer(user):
                allowed_statuses = viewer_allowed_statuses(user)
                units_obj = strategy.get_all_units(active_only=False)
                if allowed_statuses:
                    # filter in python (no strategy changes required)
                    units_obj = [u for u in units_obj if getattr(u, "status", None) in allowed_statuses]
                    
                else:
                    # if viewer has no statuses saved -> show nothing
                    units_obj = []
            else:
                # existing behavior unchanged for sales/saleshead
                units_obj = strategy.get_all_units(active_only=is_client_user)
                
            context["units"] = units_obj

            # B) units_json serialization (same rules)
            context["units_json"] = serialize_units_for_js(units_obj=units_obj, project_map=project_map)

            # C) unit search (same behavior) - only when POST has unit_query
            if unit_query:
                found_unit = strategy.get_unit(unit_query)
                

                enforcement = enforce_client_unit_rules_and_limits(
                    user=user,
                    is_client_user=is_client_user,
                    user_company=user_company,
                    found_unit=found_unit,
                    messages_api=messages_api,
                    request_for_messages=request_for_messages,
                )

                if enforcement.get("redirect_home"):
                    return {"_type": "redirect", "to": "home"}

                found_unit = enforcement.get("found_unit")
                context["unit"] = found_unit

                if found_unit:
                    context["total_uncovered_area"] = compute_total_uncovered_area(found_unit)

            # D) leads/clients json
            if is_client_user:
                leads_data = strategy.get_leads(user.email)
                context["clients"] = json.dumps(leads_data) if leads_data else "{}"
                

            # E) limits (post-load; preserves helper call behavior)
            if is_client_user:
                redirect_result = check_request_limits_after_project_load(
                    user=user,
                    context=context,
                    messages_api=messages_api,
                    request_for_messages=request_for_messages,
                )
                if redirect_result.get("redirect_home"):
                    return {"_type": "redirect", "to": "home"}

        else:
            # --- FIX FOR ADMINS: Load ALL units ---
            # If no specific company, but allowed (Admin/TeamMember), load everything.
            # Only trigger this logic if is_company_active is None (meaning no company constraint failed)
            # or if explicit admin role logic is desired.
            # Assuming Admins fall here because user_company is None.
            
            # Load ALL units for search
            units_obj = Unit.objects.select_related('company', 'project_company').all()
            context["units"] = units_obj
            
            # Load ALL projects for dropdown
            all_projects = Project.objects.all()
            context["projects"] = all_projects
            project_map = build_project_map(all_projects)
            
            context["units_json"] = serialize_units_for_js(units_obj=units_obj, project_map=project_map)

            # preserve: else branch unit search from Unit table only
            if unit_query:
                found_unit = Unit.objects.filter(unit_code=unit_query).first()
                context["unit"] = found_unit
                if found_unit:
                    context["total_uncovered_area"] = compute_total_uncovered_area(found_unit)

        # 4) Project search (same) + UPDATED tenor_range restriction
        handle_project_search_and_load_config(
            project_query=project_query or "",
            context=context,
            user_can_change_years=context.get("user_can_change_years", True),
        )

        # 5) Render rules for inactive client company (same)
        if (
            scope.is_client_user
            and scope.user_role in ["Sales","SalesHead", "Client"]
            and not context.get("is_company_active")
        ):
            return {
                "_type": "render",
                "template": "ToP/home.html",
                "context": {
                    "is_company_active": False,
                    "is_not_native_company": context.get("is_not_native_company"),
                },
            }

        return {"_type": "render", "template": "ToP/home.html", "context": context}