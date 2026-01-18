# ToP/services/unit_mapping_service.py

from __future__ import annotations

import traceback
from dataclasses import dataclass
from decimal import Decimal
from decimal import DecimalException
from typing import Any, Dict, Optional, List

from django.db import transaction
from django.shortcuts import get_object_or_404

from ..models import (
    Company,
    SalesHead,
    Manager,
    Sales,
    Project,
    ProjectWebConfiguration,
    Unit,
    UnitLayout,
    UnitPosition,
    UnitPositionChild,
)

from ..utils.unit_mapping_utils import (
    serialize_unit,
    get_role_flags_for_masterplan,
    build_masterplan_unit_data_map,
    should_filter_available_only,
    compute_display_status_for_client,
    get_layout_images,
    get_floor_sort_index,
    find_local_unit,
    unique_gallery_from_layouts,
    build_layout_manager_context,
    is_ajax,
    is_restricted_layout_user,
    extract_layout_filters,
    native_dropdown_values,
)

# NOTE: We keep viewer utils imports because you are using them already in read-only logic.
# But the NEW scoping requested here is for Uploader.
from ..utils.viewer_permissions import (
    is_company_viewer,
    viewer_company,
    viewer_allowed_statuses,
)


@dataclass
class ServiceResult:
    success: bool
    status: int = 200
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    trace: Optional[str] = None


class UnitMappingService:
    """
    Service layer for Masterplan & Unit Mapping.
    - Operates strictly on Local DB (Unit Warehouse).
    - Uploader users are company-scoped: they can see ONLY their company projects.
    - Viewer users remain restricted by existing viewer rules (already in your system).
    """

    # =========================================================
    # Uploader scoping helpers (NEW)
    # =========================================================
    @staticmethod
    def _get_uploader_company(user) -> Optional[Company]:
        """
        If the logged-in user has an uploader_profile with a company, return it.
        Otherwise return None.
        """
        uploader_profile = getattr(user, "uploader_profile", None)
        if uploader_profile and getattr(uploader_profile, "company_id", None):
            return uploader_profile.company
        return None

    @staticmethod
    def _projects_qs_for_user(user):
        """
        Returns allowed Projects queryset:
        - Uploader => only uploader company projects
        - Others   => all projects
        """
        uploader_company = UnitMappingService._get_uploader_company(user)
        if uploader_company:
            return Project.objects.filter(company=uploader_company)
        return Project.objects.all()

    @staticmethod
    def _user_can_access_project(user, project: Project) -> bool:
        """
        Hard restriction:
        - If user is Uploader => project must belong to uploader company.
        - Otherwise allow.
        (Viewer restriction is handled in read-only/masterplan logic below as you already had it.)
        """
        uploader_company = UnitMappingService._get_uploader_company(user)
        if uploader_company:
            return project.company_id == uploader_company.id
        return True

    # --------------------------
    # Page contexts
    # --------------------------
    @staticmethod
    def get_unit_mapping_page_context(*, user) -> ServiceResult:
        """
        Unit Mapping (Admin/Uploader/Team/Developer) context.
        ✅ Uploader will only see their company projects.
        """
        try:
            user_company = UnitMappingService._get_uploader_company(user)
            projects = UnitMappingService._projects_qs_for_user(user)

            payload = {"projects": projects}
            if user_company:
                payload["company"] = user_company

            return ServiceResult(True, 200, payload=payload)
        
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def get_unit_mapping_read_only_context(*, user) -> ServiceResult:
        """
        Read-only view:
        - Viewer  => ONLY viewer company projects (existing behavior)
        - Uploader => ONLY uploader company projects (NEW behavior)
        - Sales/SalesHead => company projects
        - Manager => company projects
        - Adminish => all projects
        """
        try:
            # ✅ Viewer restriction FIRST (existing behavior)
            if is_company_viewer(user):
                v_company = viewer_company(user)
                projects = Project.objects.filter(company=v_company) if v_company else Project.objects.none()
                return ServiceResult(True, 200, payload={
                    "projects": projects,
                    "company": v_company,
                    "viewer_allowed_statuses": sorted(viewer_allowed_statuses(user)),
                })

            # ✅ Uploader restriction (NEW)
            uploader_company = UnitMappingService._get_uploader_company(user)
            if uploader_company:
                projects = Project.objects.filter(company=uploader_company)
                return ServiceResult(True, 200, payload={
                    "projects": projects,
                    "company": uploader_company,
                })

            projects = Project.objects.all()
            user_company = None

            is_sales = user.groups.filter(name="Sales").exists()
            is_saleshead = user.groups.filter(name="SalesHead").exists()
            is_sales_or_head = is_sales or is_saleshead

            is_manager = user.groups.filter(name="Manager").exists()
            is_adminish = user.groups.filter(name__in=["Admin", "Developer", "TeamMember"]).exists()

            # Sales / SalesHead company restriction
            if is_sales_or_head:
                profile = None
                if is_saleshead:
                    profile = SalesHead.objects.filter(user=user).select_related("company").first()
                if not profile and is_sales:
                    profile = Sales.objects.filter(user=user).select_related("company").first()

                if profile and profile.company:
                    user_company = profile.company
                    projects = Project.objects.filter(company=user_company)

            # Manager restriction
            if is_manager:
                manager = Manager.objects.filter(user=user).select_related("company").first()
                if manager and manager.company:
                    user_company = manager.company
                    projects = Project.objects.filter(company=user_company)

            # Adminish => all
            if is_adminish:
                projects = Project.objects.all()

            return ServiceResult(True, 200, payload={"projects": projects, "company": user_company})
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    # --------------------------
    # Masterplan fetch
    # --------------------------
    @staticmethod
    def get_project_masterplan(*, user, project_id: int) -> ServiceResult:
        try:
            project = Project.objects.select_related("company").get(id=project_id)

            # ✅ Uploader restriction (NEW)
            if not UnitMappingService._user_can_access_project(user, project):
                return ServiceResult(False, 403, error="Not allowed")

            # ✅ Viewer restriction (existing)
            if is_company_viewer(user):
                v_company = viewer_company(user)
                if not v_company or project.company_id != v_company.id:
                    return ServiceResult(False, 403, error="Not allowed")

            masterplan = getattr(project, "masterplan", None)

            is_client, is_managerish = get_role_flags_for_masterplan(user)

            config = ProjectWebConfiguration.objects.filter(project=project).first()
            show_all_flag = config.show_not_availables_units_for_sales if config else True

            viewer_mode = is_company_viewer(user)
            viewer_statuses = viewer_allowed_statuses(user) if viewer_mode else None

            filter_available_only = should_filter_available_only(
                is_client=is_client,
                is_managerish=is_managerish,
                show_all_flag=show_all_flag,
            )

            # Viewers should not be forced into "Available only"
            if viewer_mode:
                filter_available_only = False

            if not (masterplan and masterplan.image):
                return ServiceResult(True, 200, payload={"has_masterplan": False})

            positions = masterplan.unit_positions.all().prefetch_related("child_units")
            unit_data_map = build_masterplan_unit_data_map(project=project)

            allowed_norm = None
            if viewer_statuses is not None:
                allowed_norm = {x.strip().lower() for x in viewer_statuses}

            unit_positions_data = []

            for pos in positions:
                current_specs = []
                display_status = "Available"

                if pos.unit_type == "single":
                    u_data = unit_data_map.get(pos.unit_code)
                    if not u_data:
                        continue

                    if allowed_norm is not None:
                        s = (u_data.get("status") or "").strip().lower()
                        if s not in allowed_norm:
                            continue

                    if filter_available_only and (u_data["status"] != "Available" or u_data["is_locked"]):
                        continue

                    display_status = compute_display_status_for_client(
                        is_client=is_client,
                        is_managerish=is_managerish,
                        raw_status=u_data["status"],
                        is_locked=u_data["is_locked"],
                    )
                    current_specs.append(u_data)

                elif pos.unit_type == "building":
                    children = pos.child_units.all()
                    has_visible_child = False

                    for child in children:
                        c_data = unit_data_map.get(child.unit_code)
                        if not c_data:
                            continue

                        if allowed_norm is not None:
                            c = (c_data.get("status") or "").strip().lower()
                            if c not in allowed_norm:
                                continue

                        if filter_available_only and (c_data["status"] != "Available" or c_data["is_locked"]):
                            continue

                        has_visible_child = True
                        current_specs.append(c_data)

                    if not has_visible_child:
                        continue

                    display_status = "Available"

                unit_positions_data.append({
                    "id": pos.id,
                    "unit_code": pos.unit_code,
                    "x_percent": pos.x_percent,
                    "y_percent": pos.y_percent,
                    "unit_type": pos.unit_type,
                    "unit_status": display_status,
                    "filter_data": current_specs,
                })

            return ServiceResult(True, 200, payload={
                "has_masterplan": True,
                "image_url": masterplan.image.url,
                "unit_positions": unit_positions_data,
                "is_client": is_client,
            })

        except Project.DoesNotExist:
            return ServiceResult(False, 404, error="Project not found")
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    # --------------------------
    # Save pin
    # --------------------------
    @staticmethod
    def save_unit_position(*, request, user) -> ServiceResult:
        try:
            if request.method != "POST":
                return ServiceResult(False, 405, error="Invalid method")

            project_id = request.POST.get("project_id")
            main_code = request.POST.get("unit_code")
            x_percent = request.POST.get("x_percent")
            y_percent = request.POST.get("y_percent")
            unit_type = request.POST.get("unit_type", "single")

            if not all([project_id, main_code, x_percent, y_percent]):
                return ServiceResult(False, 400, error="Missing required fields")

            try:
                x_percent_decimal = Decimal(x_percent)
                y_percent_decimal = Decimal(y_percent)
            except (DecimalException, TypeError, ValueError):
                return ServiceResult(False, 400, error="Invalid coordinates")

            project = Project.objects.select_related("company").get(id=project_id)

            # ✅ Uploader restriction (NEW)
            if not UnitMappingService._user_can_access_project(user, project):
                return ServiceResult(False, 403, error="Not allowed")

            masterplan = getattr(project, "masterplan", None)
            if not masterplan:
                return ServiceResult(False, 400, error="No masterplan found")

            if UnitPosition.objects.filter(masterplan=masterplan, unit_code=main_code).exists():
                return ServiceResult(False, 400, error=f'The label/code "{main_code}" is already mapped as a pin.')

            if UnitPositionChild.objects.filter(position__masterplan=masterplan, unit_code=main_code).exists():
                return ServiceResult(False, 400, error=f'The unit "{main_code}" is already mapped inside a building stack.')

            child_unit_codes: List[str] = []
            final_main_code = main_code
            current_status = None

            ref_unit = find_local_unit(main_code)
            if not ref_unit:
                return ServiceResult(False, 400, error=f'Unit "{main_code}" not found in database.')

            if ref_unit.company != project.company:
                return ServiceResult(False, 400, error=f'Unit "{main_code}" belongs to a different company.')

            final_main_code = ref_unit.unit_code
            current_status = ref_unit.status

            if unit_type == "building":
                stack_siblings = Unit.objects.filter(
                    project=project.name,
                    company=project.company,
                    sales_phasing=ref_unit.sales_phasing,
                    building_number=ref_unit.building_number,
                    unit_position=ref_unit.unit_position
                )
                if not stack_siblings.exists():
                    return ServiceResult(False, 400, error="No units found for this stack configuration in DB.")

                child_unit_codes = [u.unit_code for u in stack_siblings]

            if unit_type == "building":
                if UnitPosition.objects.filter(masterplan=masterplan, unit_code__in=child_unit_codes).exists():
                    return ServiceResult(False, 400, error="One or more units in this stack are already mapped independently.")

                if UnitPositionChild.objects.filter(position__masterplan=masterplan, unit_code__in=child_unit_codes).exists():
                    return ServiceResult(False, 400, error="One or more units in this stack are already mapped in another building.")

            with transaction.atomic():
                position = UnitPosition.objects.create(
                    masterplan=masterplan,
                    unit_code=final_main_code,
                    x_percent=x_percent_decimal,
                    y_percent=y_percent_decimal,
                    unit_type=unit_type,
                )

                if unit_type == "building":
                    for code in child_unit_codes:
                        UnitPositionChild.objects.create(position=position, unit_code=code)

            return ServiceResult(
                True, 200,
                payload={
                    "success": True,
                    "position_id": position.id,
                    "unit_code": position.unit_code,
                    "unit_type": position.unit_type,
                    "x_percent": str(position.x_percent),
                    "y_percent": str(position.y_percent),
                    "unit_status": current_status if unit_type == "single" else None,
                }
            )

        except Project.DoesNotExist:
            return ServiceResult(False, 404, error="Project not found")
        except Exception as e:
            return ServiceResult(False, 400, error=str(e), trace=traceback.format_exc())

    # --------------------------
    # Unit details for masterplan
    # --------------------------
    @staticmethod
    def get_unit_details_for_masterplan(*, user, unit_code: str) -> ServiceResult:
        try:
            is_client = user.groups.filter(name="Client").exists()
            is_managerish = user.groups.filter(name__in=["Manager", "Admin", "Developer"]).exists()
            should_hide_price = is_client and not is_managerish

            position = UnitPosition.objects.filter(unit_code=unit_code).first()
            if not position:
                return ServiceResult(False, 404, error="Unit not mapped on masterplan")

            project = position.masterplan.project

            # ✅ Uploader restriction (NEW)
            if not UnitMappingService._user_can_access_project(user, project):
                return ServiceResult(False, 403, error="Not allowed")

            # ✅ Viewer restriction (existing)
            if is_company_viewer(user):
                v_company = viewer_company(user)
                if not v_company or project.company_id != v_company.id:
                    return ServiceResult(False, 403, error="Not allowed")

            company_id = project.company.id

            if position.unit_type == "single":
                u = find_local_unit(position.unit_code)
                if not u:
                    return ServiceResult(False, 404, error="Mapped unit DB error")

                data = serialize_unit(u)
                data["layout_images"] = get_layout_images(
                    project=project,
                    b_type=u.building_type,
                    u_type=u.unit_type,
                    u_model=u.unit_model
                )

                if should_hide_price and data["is_locked"]:
                    data.pop("interest_free_unit_price", None)

                return ServiceResult(True, 200, payload={"type": "single", "data": data, "company_id": company_id})

            child_units = position.child_units.all()
            units_list: List[Dict[str, Any]] = []

            for child in child_units:
                u = find_local_unit(child.unit_code)
                if not u:
                    continue

                data = serialize_unit(u)
                data["child_id"] = child.id
                data["_sort_index"] = get_floor_sort_index(getattr(u, "floor", None))

                data["layout_images"] = get_layout_images(
                    project=project,
                    b_type=u.building_type,
                    u_type=u.unit_type,
                    u_model=u.unit_model
                )

                if should_hide_price and data["is_locked"]:
                    data.pop("interest_free_unit_price", None)

                units_list.append(data)

            units_list.sort(key=lambda x: x.get("_sort_index", 999))

            return ServiceResult(True, 200, payload={
                "type": "building",
                "building_name": position.unit_code,
                "data": units_list,
                "company_id": company_id,
            })

        except Exception as e:
            return ServiceResult(False, 404, error=str(e), trace=traceback.format_exc())

    # --------------------------
    # Deletes
    # --------------------------
    @staticmethod
    def delete_unit_position(*, request, position_id: int) -> ServiceResult:
        try:
            if request.method != "DELETE":
                return ServiceResult(False, 405, error="Invalid method")

            pos = UnitPosition.objects.get(id=position_id)
            pos.delete()
            return ServiceResult(True, 200, payload={"success": True})
        except UnitPosition.DoesNotExist:
            return ServiceResult(False, 404, error="Position not found")
        except Exception as e:
            return ServiceResult(False, 400, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def delete_child_unit(*, request, child_id: int) -> ServiceResult:
        try:
            if request.method != "DELETE":
                return ServiceResult(False, 405, error="Invalid method")

            child = get_object_or_404(UnitPositionChild, id=child_id)
            child.delete()
            return ServiceResult(True, 200, payload={"success": True})
        except Exception as e:
            return ServiceResult(False, 400, error=str(e), trace=traceback.format_exc())

    # --------------------------
    # Unit layout manager (HTML + AJAX)
    # --------------------------
    @staticmethod
    def unit_layout_manager_dispatch(*, request, user) -> ServiceResult:
        try:
            # ---------------------------------------------------------
            # Helpers: lock company for Uploader / Manager / Sales roles
            # ---------------------------------------------------------
            def locked_company_for_user():
                # 1) Uploader (NEW scoping already exists)
                uploader_company = UnitMappingService._get_uploader_company(user)
                if uploader_company:
                    return uploader_company

                # 2) Manager (treat as company scoped)
                if user.groups.filter(name="Manager").exists():
                    manager_profile = Manager.objects.filter(user=user).select_related("company").first()
                    if manager_profile and manager_profile.company:
                        return manager_profile.company

                # 3) Sales / SalesHead (optional hardening to match build_layout_manager_context)
                if user.groups.filter(name="SalesHead").exists():
                    sh = SalesHead.objects.filter(user=user).select_related("company").first()
                    if sh and sh.company:
                        return sh.company

                if user.groups.filter(name="Sales").exists():
                    s = Sales.objects.filter(user=user).select_related("company").first()
                    if s and s.company:
                        return s.company

                return None

            locked_company = locked_company_for_user()

            # ---------------------------------------------------------
            # Render (HTML)
            # ---------------------------------------------------------
            if not is_ajax(request):
                company = None
                context = build_layout_manager_context(user=user)  # existing behavior :contentReference[oaicite:3]{index=3}
                
                # 🔒 Company scoping (Uploader behaves like Manager: cannot choose company)
                if locked_company:
                    context["companies"] = [locked_company]
                    context["company"]  = locked_company
                    context["initial_company_id"] = locked_company.id

                # ✅ UI flags (NEW)
                context["is_company_scoped"] = bool(locked_company)

                # Uploader CAN manage layouts; Manager stays view-only.
                context["can_manage_layouts"] = user.groups.filter(
                    name__in=["Admin", "Developer", "TeamMember", "Uploader"]
                ).exists()

                return ServiceResult(
                    True, 200,
                    payload={"_type": "render", "template": "ToP/unit_layout_manager.html", "context": context}
                )

            # ---------------------------------------------------------
            # AJAX: Upload
            # ---------------------------------------------------------
            if request.method == "POST" and request.POST.get("action") == "upload":
                # Keep your restriction for Manager/Client, but allow Uploader explicitly
                uploader_company = UnitMappingService._get_uploader_company(user)
                if is_restricted_layout_user(user) and not uploader_company:
                    return ServiceResult(False, 403, error="Restricted users cannot upload layouts.")  # :contentReference[oaicite:4]{index=4}

                p_id = request.POST.get("project_id")
                b_type = request.POST.get("building_type")
                u_type = request.POST.get("unit_type")
                u_model = request.POST.get("unit_model")
                images = request.FILES.getlist("images")

                if not (p_id and b_type and u_type and u_model and images):
                    return ServiceResult(False, 400, error="Missing fields or images.")

                project = get_object_or_404(Project, id=p_id)

                # ✅ Hard scope: if locked_company exists, project must belong to it
                if locked_company and project.company_id != locked_company.id:
                    return ServiceResult(False, 403, error="Not allowed")

                # ✅ Preserve uploader restriction (existing helper)
                if not UnitMappingService._user_can_access_project(user, project):  # :contentReference[oaicite:5]{index=5}
                    return ServiceResult(False, 403, error="Not allowed")

                uploaded_count = 0
                for img in images:
                    exists = UnitLayout.objects.filter(
                        project=project, unit_model=u_model, image__icontains=img.name
                    ).exists()
                    if not exists:
                        UnitLayout.objects.create(
                            project=project,
                            building_type=b_type,
                            unit_type=u_type,
                            unit_model=u_model,
                            image=img,
                            uploaded_by=user,
                        )
                        uploaded_count += 1

                all_layouts = UnitLayout.objects.filter(
                    project_id=p_id, building_type=b_type, unit_type=u_type, unit_model=u_model
                ).order_by("-created_at")

                gallery = unique_gallery_from_layouts(all_layouts)

                return ServiceResult(True, 200, payload={"_type": "json", "data": {
                    "success": True,
                    "message": f"{uploaded_count} images uploaded.",
                    "gallery": gallery,
                }})

            # ---------------------------------------------------------
            # AJAX: Filtering
            # ---------------------------------------------------------
            filters = extract_layout_filters(request)

            response_data = {
                "projects": [],
                "building_types": [],
                "unit_types": [],
                "unit_models": [],
                "gallery": [],
            }

            c_id = filters["company"]
            p_id = filters["project"]
            b_type = filters["building_type"]
            u_type = filters["unit_type"]
            u_model = filters["unit_model"]

            # 🔒 If company-scoped (Uploader/Manager/Sales), force company scoping (ignore requested company)
            if locked_company:
                c_id = str(locked_company.id)

            # 1) Projects
            if c_id:
                response_data["projects"] = list(
                    Project.objects.filter(company_id=c_id).values("id", "name")
                )

            # 2) Dropdown options
            if p_id:
                project = Project.objects.filter(id=p_id).select_related("company").first()
                if not project:
                    return ServiceResult(False, 404, error="Project not found")

                # Hard scope again
                if locked_company and project.company_id != locked_company.id:
                    return ServiceResult(False, 403, error="Not allowed")

                # Preserve uploader restriction (existing helper)
                if project and not UnitMappingService._user_can_access_project(user, project):
                    return ServiceResult(False, 403, error="Not allowed")

                bt, ut, um = native_dropdown_values(
                    p_id=p_id, b_type=b_type, u_type=u_type, u_model=u_model
                )

                if not b_type:
                    response_data["building_types"] = bt
                if b_type and not u_type:
                    response_data["unit_types"] = ut
                if b_type and u_type and not u_model:
                    response_data["unit_models"] = um

            # 3) Gallery
            if p_id and b_type and u_type and u_model:
                layouts = UnitLayout.objects.filter(
                    project_id=p_id, building_type=b_type, unit_type=u_type, unit_model=u_model
                ).order_by("-created_at")
                response_data["gallery"] = unique_gallery_from_layouts(layouts)

            return ServiceResult(True, 200, payload={"_type": "json", "data": response_data})

        except Project.DoesNotExist:
            return ServiceResult(False, 404, error="Project not found", trace=traceback.format_exc())
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())


    @staticmethod
    def delete_unit_layout(*, user, layout_id: int) -> ServiceResult:
        try:
            layout = get_object_or_404(UnitLayout, id=layout_id)

            # Lock company for Uploader / Manager / Sales (same pattern as dispatch)
            locked_company = UnitMappingService._get_uploader_company(user)

            if not locked_company and user.groups.filter(name="Manager").exists():
                manager_profile = Manager.objects.filter(user=user).select_related("company").first()
                if manager_profile and manager_profile.company:
                    locked_company = manager_profile.company

            if not locked_company and user.groups.filter(name="SalesHead").exists():
                sh = SalesHead.objects.filter(user=user).select_related("company").first()
                if sh and sh.company:
                    locked_company = sh.company

            if not locked_company and user.groups.filter(name="Sales").exists():
                s = Sales.objects.filter(user=user).select_related("company").first()
                if s and s.company:
                    locked_company = s.company

            # ✅ If company-scoped, the layout’s project must match
            if locked_company and layout.project and layout.project.company_id != locked_company.id:
                return ServiceResult(False, 403, error="Not allowed")

            # ✅ Preserve existing uploader restriction
            if layout.project and not UnitMappingService._user_can_access_project(user, layout.project):
                return ServiceResult(False, 403, error="Not allowed")

            layout.delete()
            return ServiceResult(True, 200, payload={"success": True, "message": "Image deleted successfully."})

        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())




    @staticmethod
    def get_unit_pin_data(*, unit_code: str) -> ServiceResult:
        try:
            position = UnitPosition.objects.select_related('masterplan').filter(unit_code=unit_code).first()
            if not position:
                child = UnitPositionChild.objects.select_related('position__masterplan').filter(unit_code=unit_code).first()
                if child:
                    position = child.position

            if not position or not position.masterplan or not position.masterplan.image:
                return ServiceResult(False, 404, error="No masterplan or pin found for this unit.")

            payload = {
                "unit_code": unit_code,
                "masterplan_url": position.masterplan.image.url,
                "x_percent": str(position.x_percent),
                "y_percent": str(position.y_percent)
            }

            return ServiceResult(True, 200, payload=payload)

        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())
