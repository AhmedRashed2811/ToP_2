# ToP/services/unit_mapping_service.py

from __future__ import annotations

import traceback
from dataclasses import dataclass
from decimal import Decimal
from decimal import DecimalException
from typing import Any, Dict, Optional, List, Tuple

from django.db import transaction
from django.shortcuts import get_object_or_404

from ..models import (
    Company,
    CompanyManager,
    CompanyUser,
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
    - Removes dependence on live ERP calls for UI rendering.
    """

    # --------------------------
    # Page contexts
    # --------------------------
    @staticmethod
    def get_unit_mapping_page_context() -> ServiceResult:
        try:
            projects = Project.objects.all()
            return ServiceResult(True, 200, payload={"projects": projects})
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    @staticmethod
    def get_unit_mapping_read_only_context(*, user) -> ServiceResult:
        try:
            projects = Project.objects.all()
            user_company = None

            is_client = user.groups.filter(name="Client").exists()
            is_manager = user.groups.filter(name="Manager").exists()
            is_adminish = user.groups.filter(name__in=["Admin", "Developer", "TeamMember"]).exists()

            if is_client and hasattr(user, "role") and getattr(user, "role", None) == "CompanyUser":
                cu = CompanyUser.objects.filter(user=user).select_related("company").first()
                if cu and cu.company:
                    user_company = cu.company
                    projects = Project.objects.filter(company=user_company)

            if is_adminish:
                projects = Project.objects.all()

            if is_manager:
                manager = CompanyManager.objects.filter(user=user).select_related("company").first()
                if manager and manager.company:
                    user_company = manager.company
                    projects = Project.objects.filter(company=user_company)

            return ServiceResult(True, 200, payload={"projects": projects, "company": user_company})
        except Exception as e:
            return ServiceResult(False, 500, error=str(e), trace=traceback.format_exc())

    # --------------------------
    # Masterplan fetch
    # --------------------------
    @staticmethod
    def get_project_masterplan(*, user, project_id: int) -> ServiceResult:
        try:
            project = Project.objects.get(id=project_id)
            masterplan = getattr(project, "masterplan", None)

            is_client, is_managerish = get_role_flags_for_masterplan(user)

            config = ProjectWebConfiguration.objects.filter(project=project).first()
            show_all_flag = config.show_not_availables_units_for_sales if config else True
            filter_available_only = should_filter_available_only(
                is_client=is_client,
                is_managerish=is_managerish,
                show_all_flag=show_all_flag,
            )

            if not (masterplan and masterplan.image):
                return ServiceResult(True, 200, payload={"has_masterplan": False})

            positions = masterplan.unit_positions.all().prefetch_related("child_units")

            # ✅ Now builds map purely from Local DB
            unit_data_map = build_masterplan_unit_data_map(project=project)

            unit_positions_data: List[Dict[str, Any]] = []

            for pos in positions:
                current_specs: List[Dict[str, Any]] = []
                display_status = "Available"

                # --- Single unit pin ---
                if pos.unit_type == "single":
                    u_data = unit_data_map.get(pos.unit_code)
                    if not u_data:
                        continue

                    # Filter Logic
                    if filter_available_only and (u_data["status"] != "Available" or u_data["is_locked"]):
                        continue

                    display_status = compute_display_status_for_client(
                        is_client=is_client,
                        is_managerish=is_managerish,
                        raw_status=u_data["status"],
                        is_locked=u_data["is_locked"],
                    )
                    current_specs.append(u_data)

                # --- Building pin ---
                elif pos.unit_type == "building":
                    children = pos.child_units.all()
                    has_visible_child = False

                    for child in children:
                        c_data = unit_data_map.get(child.unit_code)
                        if not c_data:
                            continue

                        if filter_available_only and (c_data["status"] != "Available" or c_data["is_locked"]):
                            continue

                        has_visible_child = True
                        current_specs.append(c_data)

                    display_status = "Available"
                    if not has_visible_child and filter_available_only:
                        continue

                unit_positions_data.append({
                    "id": pos.id,
                    "unit_code": pos.unit_code,
                    "x_percent": pos.x_percent,
                    "y_percent": pos.y_percent,
                    "unit_type": pos.unit_type,
                    "unit_status": display_status,
                    "filter_data": current_specs,
                })

            return ServiceResult(
                True, 200,
                payload={
                    "has_masterplan": True,
                    "image_url": masterplan.image.url,
                    "unit_positions": unit_positions_data,
                    "is_client": is_client,
                }
            )

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

            project = Project.objects.get(id=project_id)
            masterplan = getattr(project, "masterplan", None)
            if not masterplan:
                return ServiceResult(False, 400, error="No masterplan found")

            # Duplicate checks
            if UnitPosition.objects.filter(masterplan=masterplan, unit_code=main_code).exists():
                return ServiceResult(False, 400, error=f'The label/code "{main_code}" is already mapped as a pin.')

            if UnitPositionChild.objects.filter(position__masterplan=masterplan, unit_code=main_code).exists():
                return ServiceResult(False, 400, error=f'The unit "{main_code}" is already mapped inside a building stack.')

            child_unit_codes: List[str] = []
            final_main_code = main_code
            current_status = None

            # --- UNIFIED LOCAL LOOKUP STRATEGY ---
            ref_unit = find_local_unit(main_code)
            if not ref_unit:
                return ServiceResult(False, 400, error=f'Unit "{main_code}" not found in database.')
            
            # Ensure it belongs to this project/company
            if ref_unit.company != project.company:
                 return ServiceResult(False, 400, error=f'Unit "{main_code}" belongs to a different company.')

            final_main_code = ref_unit.unit_code
            current_status = ref_unit.status

            if unit_type == "building":
                # Find stack siblings in Local DB
                # Criteria: Same project, company, sales_phasing, building_number, unit_position
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

            # Extra safety
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
            company_id = project.company.id

            # --- UNIFIED DB LOOKUP ---

            # Single pin
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

            # Building pin
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
    # Delete pin / child (No changes needed, but included for completeness)
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
            if not is_ajax(request):
                context = build_layout_manager_context(user=user)
                return ServiceResult(True, 200, payload={"_type": "render", "template": "ToP/unit_layout_manager.html", "context": context})

            # AJAX: Upload
            if request.method == "POST" and request.POST.get("action") == "upload":
                if is_restricted_layout_user(user):
                    return ServiceResult(False, 403, error="Restricted users cannot upload layouts.")

                p_id = request.POST.get("project_id")
                b_type = request.POST.get("building_type")
                u_type = request.POST.get("unit_type")
                u_model = request.POST.get("unit_model")
                images = request.FILES.getlist("images")

                if not (p_id and b_type and u_type and u_model and images):
                    return ServiceResult(False, 400, error="Missing fields or images.")

                project = get_object_or_404(Project, id=p_id)

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

            # AJAX: Filtering
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

            # 1) Projects
            if c_id:
                response_data["projects"] = list(Project.objects.filter(company_id=c_id).values("id", "name"))

            # 2) Dropdown options (Native DB only now)
            if p_id:
                bt, ut, um = native_dropdown_values(
                    p_id=p_id, b_type=b_type, u_type=u_type, u_model=u_model
                )
                
                if not b_type: response_data["building_types"] = bt
                if b_type and not u_type: response_data["unit_types"] = ut
                if b_type and u_type and not u_model: response_data["unit_models"] = um

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