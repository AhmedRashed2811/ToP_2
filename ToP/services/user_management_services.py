import csv
import json
from io import StringIO
from typing import Any, List, Optional, Dict

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import login as Login, logout as Logout
from django.contrib.auth import login as login_2
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.db.models import Q

from ..forms import CreateUserForm, CustomPasswordChangeForm
from ..models import (
    User,
    Company,
    SalesTeam,
    SalesHead,
    Sales,
    SalesOperation,
    CompanyViewer,
    Manager,
    Uploader,
    CompanyAdmin,
    Admin,
    BusinessAnalysisTeam,
)


class UserManagementService:
    """
    Service layer for all user-related flows:
    - login/logout
    - change password
    - create user
    - impersonation (login as / revert)
    - manage users (bulk + single save/delete + sorting)
    - import users from CSV
    """

    ROLE_GROUPS = {
        "Admin": ["Admin"],
        "CompanyAdmin": ["CompanyAdmin"],
        "SalesHead": ["SalesHead"],
        "Sales": ["Sales", "Client"],
        "SalesOperation": ["SalesOperation", "Controller"],
        "Manager": ["Manager"],
        "Uploader": ["Uploader"],
        "Viewer": ["Viewer"],
        "BusinessTeam": ["BusinessTeam", "TeamMember"],
    }

    ROLE_GROUPS_FLAT = sorted({g for gs in ROLE_GROUPS.values() for g in gs})

    COMPANY_LINKED_ROLES = {"CompanyAdmin", "SalesHead", "Sales", "SalesOperation", "Manager", "Uploader", "Viewer"}
    INTERNAL_ROLES = {"Admin", "BusinessTeam"}

    # ==================================================
    # Helpers
    # ==================================================
    @staticmethod
    def _ensure_groups_exist():
        for name in UserManagementService.ROLE_GROUPS_FLAT:
            Group.objects.get_or_create(name=name)

    @staticmethod
    def _add_groups(user: User, group_names: List[str]):
        UserManagementService._ensure_groups_exist()
        for name in group_names:
            g, _ = Group.objects.get_or_create(name=name)
            user.groups.add(g)

    @staticmethod
    def _clear_role_groups(user: User):
        qs = user.groups.filter(name__in=UserManagementService.ROLE_GROUPS_FLAT)
        if qs.exists():
            user.groups.remove(*list(qs))

    @staticmethod
    def _has_any_group(user: User, names: List[str]) -> bool:
        return user.is_superuser or user.groups.filter(name__in=names).exists()

    @staticmethod
    def _actor_can_manage_users(actor: User) -> bool:
        return UserManagementService._has_any_group(actor, ["Admin", "CompanyAdmin"])

    @staticmethod
    def _actor_can_impersonate(actor: User) -> bool:
        # Strict: ONLY Admin/Superuser can impersonate. CompanyAdmin cannot.
        if actor.groups.filter(name="CompanyAdmin").exists() and not actor.is_superuser:
            return False
        return UserManagementService._has_any_group(actor, ["Admin"])

    @staticmethod
    def _get_actor_company(actor: User) -> Optional[Company]:
        """Returns the company ONLY if actor is a CompanyAdmin (Admins/Superuser return None)."""
        if actor.is_superuser or actor.groups.filter(name="Admin").exists():
            return None
        if actor.groups.filter(name="CompanyAdmin").exists():
            if hasattr(actor, 'company_admin_profile') and actor.company_admin_profile and actor.company_admin_profile.company_id:
                return actor.company_admin_profile.company
        return None

    @staticmethod
    def _verify_company_access(actor: User, target_company_id: Optional[str]) -> bool:
        """
        Returns True if actor is allowed to touch target_company_id.
        Admins can touch anything. CompanyAdmins only their own.
        """
        if actor.is_superuser or actor.groups.filter(name="Admin").exists():
            return True
        
        actor_comp = UserManagementService._get_actor_company(actor)
        if not actor_comp:
            return False # Should not happen if permission checks passed
            
        # If target_company_id is None/Empty, CompanyAdmin can't assign/manage "no company" users generally,
        # but in practice we enforce they assign to THEIR company.
        if not target_company_id:
             return False

        return str(actor_comp.id) == str(target_company_id)

    @staticmethod
    def _parse_list_field(raw: Any) -> List[str]:
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        if isinstance(raw, str):
            s = raw.strip()
            if not s:
                return []
            if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            return [p.strip() for p in s.split(",") if p.strip()]
        return []

    @staticmethod
    def _safe_bool(post_data, key: str, default: bool = False) -> bool:
        val = post_data.get(key, None)
        if val is None:
            return default
        return str(val).lower() in ["true", "1", "yes", "on"]

    @staticmethod
    def _company_from_id(company_id: Optional[str]) -> Optional[Company]:
        if not company_id:
            return None
        return Company.objects.filter(id=company_id).first()

    @staticmethod
    def _team_from_id(team_id: Optional[str]) -> Optional[SalesTeam]:
        if not team_id:
            return None
        return SalesTeam.objects.filter(id=team_id).first()

    @staticmethod
    def _get_user_role_label(user: User) -> str:
        if user.is_superuser:
            return "Superuser"

        for role, groups in UserManagementService.ROLE_GROUPS.items():
            if user.groups.filter(name=groups[0]).exists():
                return role

        # Fallback profile check
        if hasattr(user, "admin_profile"): return "Admin"
        if hasattr(user, "company_admin_profile"): return "CompanyAdmin"
        if hasattr(user, "sales_head_profile"): return "SalesHead"
        if hasattr(user, "sales_profile"): return "Sales"
        if hasattr(user, "sales_ops_profile"): return "SalesOperation"
        if hasattr(user, "manager_profile"): return "Manager"
        if hasattr(user, "uploader_profile"): return "Uploader"
        if hasattr(user, "viewer_profile"): return "Viewer"
        if hasattr(user, "business_team_profile"): return "BusinessTeam"

        return "—"

    @staticmethod
    def _get_user_company_name(user: User) -> str:
        cid = UserManagementService._get_user_company_id(user)
        if cid:
            c = Company.objects.filter(id=cid).first()
            return c.name if c else ""
        return ""

    @staticmethod
    def _get_user_company_id(user: User) -> Optional[str]:
        for attr in [
            "sales_profile", "sales_ops_profile", "manager_profile",
            "uploader_profile", "viewer_profile", "company_admin_profile",
            "sales_head_profile",
        ]:
            if hasattr(user, attr):
                prof = getattr(user, attr)
                if prof and getattr(prof, "company_id", None):
                    return str(prof.company_id)
        return None

    @staticmethod
    def _cleanup_other_profiles(user: User, keep_role: str):
        role_to_profile_attr = {
            "Admin": "admin_profile",
            "CompanyAdmin": "company_admin_profile",
            "SalesHead": "sales_head_profile",
            "Sales": "sales_profile",
            "SalesOperation": "sales_ops_profile",
            "Manager": "manager_profile",
            "Uploader": "uploader_profile",
            "Viewer": "viewer_profile",
            "BusinessTeam": "business_team_profile",
        }
        keep_attr = role_to_profile_attr.get(keep_role)
        for role, attr in role_to_profile_attr.items():
            if attr == keep_attr:
                continue
            if hasattr(user, attr):
                try:
                    getattr(user, attr).delete()
                except Exception:
                    pass

    @staticmethod
    def _increment_company_users(company: Optional[Company]):
        if not company: return
        company.num_users = (company.num_users or 0) + 1
        company.save(update_fields=["num_users"])

    @staticmethod
    def _decrement_company_users(company: Optional[Company]):
        if not company: return
        company.num_users = max((company.num_users or 0) - 1, 0)
        company.save(update_fields=["num_users"])

    @staticmethod
    def _company_count_reconcile(old_company, new_company, old_role, new_role):
        old_is_company = old_role in UserManagementService.COMPANY_LINKED_ROLES
        new_is_company = new_role in UserManagementService.COMPANY_LINKED_ROLES

        if old_is_company and not new_is_company:
            if old_company: UserManagementService._decrement_company_users(old_company)
            return

        if not old_is_company and new_is_company:
            if new_company: UserManagementService._increment_company_users(new_company)
            return

        if old_is_company and new_is_company:
            if old_company and new_company and old_company.id != new_company.id:
                UserManagementService._decrement_company_users(old_company)
                UserManagementService._increment_company_users(new_company)

    @staticmethod
    def _is_ajax(request) -> bool:
        return request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # ==================================================
    # LOGIN / LOGOUT
    # ==================================================
    @staticmethod
    def login(*, method, post_data, request):
        if method == "POST":
            email = post_data.get("username")
            password = post_data.get("password")
            user = authenticate(request, email=email, password=password)
            if user is not None:
                Login(request, user)
                return {"redirect": "home"}
            return {"context": {"error_message": "Invalid email or password."}}
        return {"context": {}}

    @staticmethod
    def logout(*, request):
        Logout(request)

    # ==================================================
    # CHANGE PASSWORD
    # ==================================================
    @staticmethod
    def change_password(*, user, method, post_data, request):
        user_company = None
        # Helpers to find company context for the template
        for attr in ["manager_profile", "sales_head_profile", "sales_profile", 
                     "sales_ops_profile", "company_admin_profile", "uploader_profile", "viewer_profile"]:
             if hasattr(user, attr) and getattr(user, attr).company:
                 user_company = getattr(user, attr).company
                 break

        if method == "POST":
            form = CustomPasswordChangeForm(user=user, data=post_data)
            if form.is_valid():
                updated_user = form.save()
                update_session_auth_hash(request, updated_user)
                return {
                    "redirect": "home",
                    "message": "Your password was successfully updated!",
                    "message_level": "success",
                    "context": {"form": CustomPasswordChangeForm(user=user), "company": user_company},
                }
            return {
                "message": "Please correct the error below.",
                "message_level": "error",
                "context": {"form": form, "company": user_company},
            }
        return {"context": {"form": CustomPasswordChangeForm(user=user), "company": user_company}}


    # ==================================================
    # CREATE USER
    # ==================================================
    @staticmethod
    def _apply_create_user_form_restrictions(form: CreateUserForm, actor_company: Optional[Company]):
        """Restrict CreateUserForm fields for CompanyAdmin to their company only (UI helper; server still enforces)."""
        if not actor_company:
            return
        # Company dropdown => only their company
        if 'company' in form.fields:
            try:
                form.fields['company'].queryset = Company.objects.filter(id=actor_company.id)
            except Exception:
                pass
        # Team dropdown => only their company teams
        if 'team' in form.fields:
            try:
                form.fields['team'].queryset = SalesTeam.objects.filter(company=actor_company).order_by('name')
            except Exception:
                pass
        # Role dropdown => remove internal roles
        if 'role' in form.fields:
            try:
                allowed = UserManagementService.COMPANY_LINKED_ROLES
                form.fields['role'].choices = [(v, lbl) for (v, lbl) in form.fields['role'].choices if v in allowed]
            except Exception:
                pass

    @staticmethod
    def create_user(*, actor, method, post_data):
        messages_out = []
        if not UserManagementService._actor_can_manage_users(actor):
            messages_out.append({"level": "error", "text": "You do not have permission to create users."})
            return {"redirect": "home", "messages": messages_out}

        actor_company = UserManagementService._get_actor_company(actor)
        is_company_admin = (actor_company is not None)

        if method == "POST":
            
            data = post_data

            # ✅ IMPORTANT: disabled fields don't submit => force company for CompanyAdmin
            if is_company_admin and actor_company:
                data = post_data.copy()           # QueryDict -> mutable copy
                data["company"] = str(actor_company.id)
                
        
            form = CreateUserForm(post_data)
            # UI-level restrictions for CompanyAdmin (server still enforces below)
            UserManagementService._apply_create_user_form_restrictions(form, actor_company)

            if form.is_valid():
                role = (form.cleaned_data.get("role") or "").strip()
                company = form.cleaned_data.get("company")

                if is_company_admin:
                    # CompanyAdmin cannot create internal roles or superusers
                    if role in UserManagementService.INTERNAL_ROLES or role == "Superuser":
                        messages_out.append({"level": "error", "text": "You cannot create Internal users."})
                        return {"messages": messages_out, "context": {"form": form, "is_company_admin": True, "actor_company_id": actor_company.id}}

                    # CompanyAdmin must assign users to THEIR company
                    if (not company) or (str(company.id) != str(actor_company.id)):
                        messages_out.append({"level": "error", "text": "You can only create users for your company."})
                        return {"messages": messages_out, "context": {"form": form, "is_company_admin": True, "actor_company_id": actor_company.id}}

                new_user = form.save(commit=False)
                new_user.set_password(form.cleaned_data["password"])
                new_user.save()

                final_data = form.cleaned_data.copy()
                if is_company_admin:
                    final_data["company"] = actor_company

                UserManagementService._assign_role_profile_and_groups(new_user, role, final_data)

                messages_out.append({"level": "success", "text": "User created successfully!"})
                fresh = CreateUserForm()
                UserManagementService._apply_create_user_form_restrictions(fresh, actor_company)
                return {
                    "redirect": "create_user",
                    "messages": messages_out,
                    "context": {"form": fresh, "is_company_admin": is_company_admin, "actor_company_id": (actor_company.id if actor_company else None)},
                }

            for field, errs in form.errors.items():
                messages_out.append({"level": "error", "text": f"{field}: {errs}"})
            return {"messages": messages_out, "context": {"form": form, "is_company_admin": is_company_admin, "actor_company_id": (actor_company.id if actor_company else None)}}

        # GET
        form = CreateUserForm()
        UserManagementService._apply_create_user_form_restrictions(form, actor_company)
        return {"context": {"form": form, "is_company_admin": is_company_admin, "actor_company_id": (actor_company.id if actor_company else None)}}

    @staticmethod
    def _assign_role_profile_and_groups(new_user: User, role: str, cleaned: dict):
        role = (role or "").strip()
        UserManagementService._clear_role_groups(new_user)
        company = cleaned.get("company")
        team = cleaned.get("team", None)

        if role == "BusinessTeam":
            BusinessAnalysisTeam.objects.create(
                user=new_user,
                joining_date=cleaned.get("joining_date") or now().date(),
                job_title=cleaned.get("job_title") or "",
            )
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["BusinessTeam"])
            UserManagementService._cleanup_other_profiles(new_user, "BusinessTeam")
            return

        if role == "Admin":
            Admin.objects.create(
                user=new_user,
                joining_date=cleaned.get("joining_date") or now().date(),
            )
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["Admin"])
            UserManagementService._cleanup_other_profiles(new_user, "Admin")
            return

        # Company Roles
        if role == "SalesHead":
            SalesHead.objects.create(
                user=new_user, company=company, team=team,
                one_dp_only=bool(cleaned.get("one_dp_only", False)),
            )
            UserManagementService._increment_company_users(company)
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["SalesHead"])
            UserManagementService._cleanup_other_profiles(new_user, "SalesHead")
            return

        if role == "Sales":
            Sales.objects.create(
                user=new_user, company=company, team=team,
                can_edit=bool(cleaned.get("can_edit", False)),
                can_change_years=bool(cleaned.get("can_change_years", False)),
            )
            UserManagementService._increment_company_users(company)
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["Sales"])
            UserManagementService._cleanup_other_profiles(new_user, "Sales")
            return

        if role == "SalesOperation":
            editable_unit_fields = cleaned.get("editable_unit_fields", [])
            SalesOperation.objects.create(
                user=new_user, company=company,
                editable_unit_fields=editable_unit_fields or [],
            )
            UserManagementService._increment_company_users(company)
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["SalesOperation"])
            UserManagementService._cleanup_other_profiles(new_user, "SalesOperation")
            return

        if role == "Manager":
            Manager.objects.create(user=new_user, company=company)
            UserManagementService._increment_company_users(company)
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["Manager"])
            UserManagementService._cleanup_other_profiles(new_user, "Manager")
            return

        if role == "Uploader":
            Uploader.objects.create(user=new_user, company=company)
            UserManagementService._increment_company_users(company)
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["Uploader"])
            UserManagementService._cleanup_other_profiles(new_user, "Uploader")
            return

        if role == "Viewer":
            allowed_pages = cleaned.get("allowed_pages", [])
            CompanyViewer.objects.create(
                user=new_user, company=company,
                allowed_pages=allowed_pages or [],
            )
            UserManagementService._increment_company_users(company)
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["Viewer"])
            UserManagementService._cleanup_other_profiles(new_user, "Viewer")
            return

        if role == "CompanyAdmin":
            CompanyAdmin.objects.create(user=new_user, company=company)
            UserManagementService._increment_company_users(company)
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["CompanyAdmin"])
            UserManagementService._cleanup_other_profiles(new_user, "CompanyAdmin")
            return

        UserManagementService._cleanup_other_profiles(new_user, keep_role="")

    # ==================================================
    # IMPERSONATION
    # ==================================================
    @staticmethod
    def login_as_user(*, actor, method, post_data, request):
        messages_out = []
        if not UserManagementService._actor_can_impersonate(actor):
            messages_out.append({"level": "error", "text": "You do not have permission to impersonate users."})
            return {"redirect": "manage_users", "messages": messages_out}

        if method != "POST":
            return {"redirect": "manage_users", "messages": messages_out}

        user_id = post_data.get("user_id")
        target_user = get_object_or_404(User, id=user_id)

        if target_user.is_superuser:
            messages_out.append({"level": "error", "text": "You cannot login as a superuser."})
            return {"redirect": "manage_users", "messages": messages_out}

        impersonator_id = actor.id
        request.session.flush()
        request.session["impersonator_id"] = impersonator_id
        login_2(request, target_user)

        messages_out.append({"level": "success", "text": f"You are now logged in as {target_user.full_name}."})
        return {"redirect": "home", "messages": messages_out}

    @staticmethod
    def revert_impersonation(*, request):
        messages_out = []
        impersonator_id = request.session.pop("impersonator_id", None)
        if impersonator_id:
            request.session.flush()
            admin_user = get_object_or_404(User, id=impersonator_id)
            login_2(request, admin_user)
            messages_out.append({"level": "success", "text": "Returned to admin account."})

        return {"redirect": "manage_users", "messages": messages_out}

    # ==================================================
    # MANAGE USERS
    # ==================================================
    @staticmethod
    def manage_users(*, actor, method, post_data, request=None):
        messages_out = []
        if not UserManagementService._actor_can_manage_users(actor):
            messages_out.append({"level": "error", "text": "You do not have permission to manage users."})
            return {"redirect": "home", "messages": messages_out}

        is_ajax = bool(request and UserManagementService._is_ajax(request))
        actor_company = UserManagementService._get_actor_company(actor)
        is_company_admin = (actor_company is not None)

        if method == "POST":
            action = post_data.get("action")

            # --- BULK ACTIONS ---
            if action in ["activate_all_sales", "deactivate_all_sales"]:
                target_company_name = post_data.get("target_company")
                # Restrict Company Admin to own company
                if is_company_admin and target_company_name != actor_company.name:
                     messages_out.append({"level": "error", "text": "Permission Denied."})
                     return {"redirect": "manage_users", "messages": messages_out}

                is_active = (action == "activate_all_sales")
                if target_company_name:
                    count = User.objects.filter(sales_profile__company__name=target_company_name).update(is_active=is_active)
                    status = "activated" if is_active else "deactivated"
                    msg_level = "success" if is_active else "warning"
                    messages_out.append({"level": msg_level, "text": f"Successfully {status} {count} Sales users for {target_company_name}."})
                return {"redirect": "manage_users", "messages": messages_out}

            # --- SINGLE USER ACTIONS ---
            user_id = post_data.get("user_id")
            target = get_object_or_404(User, id=user_id)

            # SECURITY: Non-superusers cannot modify/delete superusers
            if target.is_superuser and not actor.is_superuser:
                if is_ajax: return JsonResponse({"ok": False, "message": "Cannot manage superuser"}, status=403)
                messages_out.append({"level": "error", "text": "Permission Denied."})
                return {"redirect": "manage_users", "messages": messages_out}

            # SECURITY: Check if CompanyAdmin is touching a valid user
            if is_company_admin:
                if target.is_superuser:
                    if is_ajax: return JsonResponse({"ok": False, "message": "Cannot manage superuser"}, status=403)
                    messages_out.append({"level": "error", "text": "Permission Denied."})
                    return {"redirect": "manage_users", "messages": messages_out}
                
                # Check target user's company
                t_comp_id = UserManagementService._get_user_company_id(target)
                if not t_comp_id or t_comp_id != str(actor_company.id):
                    if is_ajax: return JsonResponse({"ok": False, "message": "User not in your company"}, status=403)
                    messages_out.append({"level": "error", "text": "Permission Denied: User not in your company."})
                    return {"redirect": "manage_users", "messages": messages_out}

            if action == "save":
                try:
                    # Enforce company restriction on save
                    UserManagementService._update_user_from_post(target, post_data, actor_company)
                    if is_ajax: return JsonResponse({"ok": True})
                    messages_out.append({"level": "success", "text": f'User "{target.full_name}" updated successfully!'})
                    return {"redirect": "manage_users", "messages": messages_out}
                except Exception as e:
                    if is_ajax: return JsonResponse({"ok": False, "message": str(e)}, status=400)
                    messages_out.append({"level": "error", "text": f"Save failed: {e}"})
                    return {"redirect": "manage_users", "messages": messages_out}

            if action == "delete":
                full_name = target.full_name
                old_role = UserManagementService._get_user_role_label(target)
                old_company_id = UserManagementService._get_user_company_id(target)
                old_company = Company.objects.filter(id=old_company_id).first() if old_company_id else None

                if old_role in UserManagementService.COMPANY_LINKED_ROLES and old_company:
                    UserManagementService._decrement_company_users(old_company)

                target.delete()
                if is_ajax: return JsonResponse({"ok": True})
                messages_out.append({"level": "success", "text": f'User "{full_name}" deleted successfully!'})
                return {"redirect": "manage_users", "messages": messages_out}

        context = UserManagementService._build_manage_users_context(actor, actor_company)
        return {"context": context, "messages": messages_out}

    @staticmethod
    def _update_user_from_post(user: User, post_data, actor_company: Optional[Company] = None):
        # Basic fields
        user.full_name = post_data.get("full_name", user.full_name)
        user.email = post_data.get("email", user.email)
        password = post_data.get("password")
        if password:
            user.set_password(password)
        user.is_active = (post_data.get("is_active", "false") == "true")
        user.save()

        # State transition
        old_role = UserManagementService._get_user_role_label(user)
        old_company_id = UserManagementService._get_user_company_id(user)
        old_company = Company.objects.filter(id=old_company_id).first() if old_company_id else None

        new_role = (post_data.get("role") or "").strip()
        
        # If company admin, FORCE company ID to be theirs
        if actor_company:
            company_id = str(actor_company.id)
            # Company Admin cannot set internal roles
            if new_role in UserManagementService.INTERNAL_ROLES:
                raise ValueError("Permission Denied: Invalid Role")
        else:
            company_id = post_data.get("company_id")
            
        team_id = post_data.get("team_id")
        new_company = UserManagementService._company_from_id(company_id)
        team = UserManagementService._team_from_id(team_id)

        # Clear groups
        UserManagementService._clear_role_groups(user)

        # Removed role
        if not new_role or new_role == "—":
            if actor_company:
                raise ValueError("Permission Denied: CompanyAdmin cannot remove a user's role.")
            UserManagementService._company_count_reconcile(old_company, None, old_role, "")
            UserManagementService._cleanup_other_profiles(user, keep_role="")
            return

        if old_role != new_role:
            UserManagementService._cleanup_other_profiles(user, keep_role=new_role)

        UserManagementService._company_count_reconcile(old_company, new_company, old_role, new_role)

        # Specific Role Logic
        if new_role == "BusinessTeam":
            job_title = post_data.get("job_title", "")
            joining_date = post_data.get("joining_date") or now().date()
            BusinessAnalysisTeam.objects.update_or_create(user=user, defaults={"job_title": job_title, "joining_date": joining_date})
            UserManagementService._add_groups(user, UserManagementService.ROLE_GROUPS["BusinessTeam"])
            UserManagementService._cleanup_other_profiles(user, "BusinessTeam")
            return

        if new_role == "Admin":
            joining_date = post_data.get("joining_date") or now().date()
            Admin.objects.update_or_create(user=user, defaults={"joining_date": joining_date})
            UserManagementService._add_groups(user, UserManagementService.ROLE_GROUPS["Admin"])
            UserManagementService._cleanup_other_profiles(user, "Admin")
            return

        if new_role == "CompanyAdmin":
            CompanyAdmin.objects.update_or_create(user=user, defaults={"company": new_company})
            UserManagementService._add_groups(user, UserManagementService.ROLE_GROUPS["CompanyAdmin"])
            UserManagementService._cleanup_other_profiles(user, "CompanyAdmin")
            return

        if new_role == "SalesHead":
            one_dp_only = UserManagementService._safe_bool(post_data, "one_dp_only", False)
            SalesHead.objects.update_or_create(user=user, defaults={"company": new_company, "team": team, "one_dp_only": one_dp_only})
            UserManagementService._add_groups(user, UserManagementService.ROLE_GROUPS["SalesHead"])
            UserManagementService._cleanup_other_profiles(user, "SalesHead")
            return

        if new_role == "Sales":
            can_edit = UserManagementService._safe_bool(post_data, "can_edit", False)
            can_change_years = UserManagementService._safe_bool(post_data, "can_change_years", False)
            Sales.objects.update_or_create(user=user, defaults={"company": new_company, "team": team, "can_edit": can_edit, "can_change_years": can_change_years})
            UserManagementService._add_groups(user, UserManagementService.ROLE_GROUPS["Sales"])
            UserManagementService._cleanup_other_profiles(user, "Sales")
            return

        if new_role == "SalesOperation":
            raw_fields = post_data.get("editable_unit_fields") or post_data.get("editable_unit_fields_json") or ""
            editable_unit_fields = UserManagementService._parse_list_field(raw_fields)
            SalesOperation.objects.update_or_create(user=user, defaults={"company": new_company, "editable_unit_fields": editable_unit_fields})
            UserManagementService._add_groups(user, UserManagementService.ROLE_GROUPS["SalesOperation"])
            UserManagementService._cleanup_other_profiles(user, "SalesOperation")
            return

        if new_role == "Manager":
            Manager.objects.update_or_create(user=user, defaults={"company": new_company})
            UserManagementService._add_groups(user, UserManagementService.ROLE_GROUPS["Manager"])
            UserManagementService._cleanup_other_profiles(user, "Manager")
            return

        if new_role == "Uploader":
            Uploader.objects.update_or_create(user=user, defaults={"company": new_company})
            UserManagementService._add_groups(user, UserManagementService.ROLE_GROUPS["Uploader"])
            UserManagementService._cleanup_other_profiles(user, "Uploader")
            return

        if new_role == "Viewer":
            raw_pages = post_data.get("allowed_pages") or post_data.get("allowed_pages_json") or ""
            allowed_pages = UserManagementService._parse_list_field(raw_pages)
            CompanyViewer.objects.update_or_create(user=user, defaults={"company": new_company, "allowed_pages": allowed_pages})
            UserManagementService._add_groups(user, UserManagementService.ROLE_GROUPS["Viewer"])
            UserManagementService._cleanup_other_profiles(user, "Viewer")
            return

        UserManagementService._cleanup_other_profiles(user, keep_role="")

    @staticmethod
    def _build_manage_users_context(actor: User, actor_company: Optional[Company]):
        role_order = {
            "Superuser": 0, "Admin": 1, "CompanyAdmin": 2, "SalesHead": 3,
            "Manager": 4, "SalesOperation": 5, "Sales": 6, "Uploader": 7,
            "Viewer": 8, "BusinessTeam": 9, "—": 99,
        }

        qs = User.objects.select_related(
            "sales_profile__company", "sales_profile__team",
            "sales_ops_profile__company", "manager_profile__company",
            "uploader_profile__company", "viewer_profile__company",
            "company_admin_profile__company", "sales_head_profile__company",
            "sales_head_profile__team", "admin_profile", "business_team_profile",
        )

        # CompanyAdmin: only their company, no superusers, no internal users
        if actor_company:
            qs = qs.exclude(is_superuser=True)
            qs = qs.exclude(groups__name__in=["Admin", "BusinessTeam", "TeamMember"])
            qs = qs.exclude(Q(admin_profile__isnull=False) | Q(business_team_profile__isnull=False))
            qs = qs.filter(
                Q(sales_profile__company=actor_company) |
                Q(sales_head_profile__company=actor_company) |
                Q(sales_ops_profile__company=actor_company) |
                Q(manager_profile__company=actor_company) |
                Q(uploader_profile__company=actor_company) |
                Q(viewer_profile__company=actor_company) |
                Q(company_admin_profile__company=actor_company)
            )

        users = list(qs.all())
        for u in users:
            u.role_label = UserManagementService._get_user_role_label(u)
            u.company_name = UserManagementService._get_user_company_name(u)
            u.company_id = UserManagementService._get_user_company_id(u)

        sorted_users = sorted(
            users,
            key=lambda u: (
                role_order.get(getattr(u, "role_label", "—"), 99),
                (getattr(u, "company_name", "") or "").lower(),
                (u.full_name or "").lower(),
            ),
        )

        if actor_company:
            companies = Company.objects.filter(id=actor_company.id)
            teams = SalesTeam.objects.filter(company=actor_company).order_by("name")
        else:
            companies = Company.objects.all().order_by("name")
            teams = SalesTeam.objects.select_related("company").all().order_by("company__name", "name")

        return {
            "users": sorted_users,
            "companies": companies,
            "teams": teams,
            "roles": list(UserManagementService.ROLE_GROUPS.keys()),
            "is_company_admin": bool(actor_company),
            "actor_company_id": (actor_company.id if actor_company else None),
        }

    # ==================================================
    # IMPORT SALES USERS (CSV)
    # ==================================================
    @staticmethod
    def import_company_users(*, actor, method, files, post_data):
        if not UserManagementService._actor_can_manage_users(actor):
            return {"status": 403, "payload": {"message": "You do not have permission to import users."}}

        if method != "POST" or not files.get("csv_file"):
            return {"status": 400, "payload": {"message": "Invalid request"}}

        company_id = post_data.get("company_id")
        if not company_id:
            return {"status": 400, "payload": {"message": "Company ID is required."}}
            
        # Permission check
        if not UserManagementService._verify_company_access(actor, company_id):
             return {"status": 403, "payload": {"message": "You cannot import users for another company."}}

        company = Company.objects.filter(id=company_id).first()
        if not company:
            return {"status": 404, "payload": {"message": "Company not found."}}

        decoded_file = files["csv_file"].read().decode("utf-8")
        reader = csv.DictReader(StringIO(decoded_file))

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for row in reader:
            email = row.get("Email")
            full_name = row.get("Name")
            raw_password = row.get("Password")

            can_edit_bool = str(row.get("Can Edit", "False")).lower() == "true"
            can_change_years_bool = str(row.get("Can Change Years", "False")).lower() == "true"

            team_name = row.get("Team") or row.get("Team Name") or ""
            team = None
            if team_name:
                team = SalesTeam.objects.filter(company=company, name__iexact=team_name.strip()).first()

            if not email or not full_name or not raw_password:
                skipped_count += 1
                continue

            existing = User.objects.filter(email=email).first()

            if existing:
                # Security: if existing user belongs to another company, prevent overwrite?
                # For now, assuming email uniqueness implies ownership, but let's be safe:
                existing_cid = UserManagementService._get_user_company_id(existing)
                if existing_cid and existing_cid != str(company.id):
                    # Skip if user exists in another company
                    skipped_count += 1
                    continue
                
                existing.full_name = full_name
                existing.password = make_password(raw_password)
                existing.save()

                UserManagementService._clear_role_groups(existing)
                UserManagementService._cleanup_other_profiles(existing, keep_role="Sales")

                Sales.objects.update_or_create(
                    user=existing,
                    defaults={
                        "company": company, "team": team,
                        "can_edit": can_edit_bool, "can_change_years": can_change_years_bool,
                    },
                )
                UserManagementService._add_groups(existing, UserManagementService.ROLE_GROUPS["Sales"])
                updated_count += 1
                continue

            new_user = User.objects.create(email=email, full_name=full_name, password=make_password(raw_password))
            Sales.objects.create(
                user=new_user, company=company, team=team,
                can_edit=can_edit_bool, can_change_years=can_change_years_bool,
            )
            UserManagementService._add_groups(new_user, UserManagementService.ROLE_GROUPS["Sales"])
            UserManagementService._cleanup_other_profiles(new_user, "Sales")
            UserManagementService._increment_company_users(company)
            created_count += 1

        return {
            "status": 200,
            "payload": {
                "message": (f"Import completed. Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}")
            },
        }