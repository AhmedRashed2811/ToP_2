import csv
from io import StringIO

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404

from ..forms import CreateUserForm, CustomPasswordChangeForm
from ..models import (
    User,
    Company,
    CompanyUser,
    CompanyController,
    CompanyManager,
    CompanyFinanceManager,
    BusinessAnalysisTeam,
)


from django.contrib.auth import authenticate, login as Login, logout as Logout
from django.contrib.auth import login as login_2



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

            return {
                "context": {"error_message": "Invalid email or password."}
            }

        return {"context": {}}

    @staticmethod
    def logout(*, request):
        Logout(request)

    # ==================================================
    # CHANGE PASSWORD
    # ==================================================
    @staticmethod
    def change_password(*, user, method, post_data, request):
        if method == "POST":
            form = CustomPasswordChangeForm(user=user, data=post_data)
            if form.is_valid():
                updated_user = form.save()
                update_session_auth_hash(request, updated_user)
                return {
                    "redirect": "home",
                    "message": "Your password was successfully updated!",
                    "message_level": "success",
                    "context": {"form": CustomPasswordChangeForm(user=user)},
                }
            return {
                "message": "Please correct the error below.",
                "message_level": "error",
                "context": {"form": form},
            }

        return {"context": {"form": CustomPasswordChangeForm(user=user)}}

    # ==================================================
    # CREATE USER
    # ==================================================
    @staticmethod
    def create_user(*, actor, method, post_data):
        messages_out = []

        # Your original permission check (kept)
        if not (actor.is_superuser or getattr(actor, "role", "") in ["Admin", "Developer"]):
            messages_out.append({"level": "error", "text": "You do not have permission to create users."})
            return {"redirect": "home", "messages": messages_out}

        if method == "POST":
            form = CreateUserForm(post_data)
            if form.is_valid():
                new_user = form.save(commit=False)
                new_user.set_password(form.cleaned_data["password"])
                new_user.save()

                role = form.cleaned_data["role"]
                UserManagementService._assign_role_profile_and_groups(new_user, role, form.cleaned_data)

                messages_out.append({"level": "success", "text": "User created successfully!"})
                return {
                    "redirect": "create_user",
                    "messages": messages_out,
                    "context": {"form": CreateUserForm()},
                }

            # show field errors like your original
            for field, errs in form.errors.items():
                messages_out.append({"level": "error", "text": f"{field}: {errs}"})

            return {"messages": messages_out, "context": {"form": form}}

        return {"context": {"form": CreateUserForm()}}

    @staticmethod
    def _assign_role_profile_and_groups(new_user, role, cleaned):
        """
        Encapsulates your role-specific creation logic.
        Preserves behavior from your original view.
        """
        if role == "BusinessTeam":
            BusinessAnalysisTeam.objects.create(
                user=new_user,
                joining_date=cleaned.get("joining_date"),
                job_title=cleaned.get("job_title"),
            )
            new_user.groups.add(Group.objects.get(name="TeamMember"))

        elif role == "CompanyUser":
            company = cleaned.get("company")
            can_edit = cleaned.get("can_edit", False)
            can_change_years = cleaned.get("can_change_years", False)
            CompanyUser.objects.create(user=new_user, company=company, can_edit=can_edit, can_change_years = can_change_years)
            company.num_users += 1
            company.save(update_fields=["num_users"])
            new_user.groups.add(Group.objects.get(name="Client"))

        elif role == "CompanyController":
            company = cleaned.get("company")
            CompanyController.objects.create(user=new_user, company=company)
            company.num_users += 1
            company.save(update_fields=["num_users"])
            new_user.groups.add(Group.objects.get(name="Controller"))

        elif role == "Manager":
            company = cleaned.get("company")
            CompanyManager.objects.create(user=new_user, company=company)
            company.num_users += 1
            company.save(update_fields=["num_users"])
            new_user.groups.add(Group.objects.get(name="Manager"))
            
        elif role == "CompanyFinanceManager":
            company = cleaned.get("company")
            CompanyFinanceManager.objects.create(user=new_user, company=company)

            company.num_users += 1
            company.save(update_fields=["num_users"])

            # ✅ add to Auth Group named exactly: "FinancemManager"
            new_user.groups.add(Group.objects.get(name="FinanceManager"))

        # If Developer, assign Business Team profile + Developer group
        if role == "Developer":
            BusinessAnalysisTeam.objects.create(
                user=new_user,
                joining_date=cleaned.get("joining_date"),
                job_title=cleaned.get("job_title"),
            )
            new_user.groups.add(Group.objects.get(name="Developer"))

        # If Admin, set role + Admin group
        if role == "Admin":
            new_user.role = "Admin"
            new_user.save(update_fields=["role"])
            new_user.groups.add(Group.objects.get(name="Admin"))

    # ==================================================
    # IMPERSONATION
    # ==================================================
    @staticmethod
    def login_as_user(*, actor, method, post_data, request):
        messages_out = []
        if method != "POST":
            return {"redirect": "manage_users", "messages": messages_out}

        user_id = post_data.get("user_id")
        target_user = get_object_or_404(User, id=user_id)

        if target_user.is_superuser:
            messages_out.append({"level": "error", "text": "You cannot login as a superuser."})
            return {"redirect": "manage_users", "messages": messages_out}

        impersonator_id = actor.id

        # Flush session to prevent stale data
        request.session.flush()

        # Restore impersonator info
        request.session["impersonator_id"] = impersonator_id

        # Log in as target user
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
    def manage_users(*, actor, method, post_data):
        messages_out = []

        if method == "POST":
            action = post_data.get("action")

            # Bulk activation
            if action == "activate_all_sales":
                target_company_name = post_data.get("target_company")
                if target_company_name:
                    count = User.objects.filter(companyuser__company__name=target_company_name).update(is_active=True)
                    messages_out.append({"level": "success", "text": f"Successfully activated {count} Sales users for {target_company_name}."})
                return {"redirect": "manage_users", "messages": messages_out}

            # Bulk deactivation
            if action == "deactivate_all_sales":
                target_company_name = post_data.get("target_company")
                if target_company_name:
                    count = User.objects.filter(companyuser__company__name=target_company_name).update(is_active=False)
                    messages_out.append({"level": "warning", "text": f"Successfully deactivated {count} Sales users for {target_company_name}."})
                return {"redirect": "manage_users", "messages": messages_out}

            # Single user actions
            user_id = post_data.get("user_id")
            target = get_object_or_404(User, id=user_id)

            if action == "save":
                UserManagementService._update_user_from_post(target, post_data)
                messages_out.append({"level": "success", "text": f'User "{target.full_name}" updated successfully!'})
                return {"redirect": "manage_users", "messages": messages_out}

            if action == "delete":
                full_name = target.full_name
                target.delete()
                messages_out.append({"level": "success", "text": f'User "{full_name}" deleted successfully!'})
                return {"redirect": "manage_users", "messages": messages_out}

        # GET context
        context = UserManagementService._build_manage_users_context()
        return {"context": context, "messages": messages_out}

    @staticmethod
    def _update_user_from_post(user, post_data):
        user.full_name = post_data.get("full_name")
        user.email = post_data.get("email")
        user.role = post_data.get("role")

        password = post_data.get("password")
        if password:
            user.set_password(password)

        user.is_active = (post_data.get("is_active", "false") == "true")

        role = user.role
        company_id = post_data.get("company_id")

        # CompanyUser (can_edit)
        if role == "CompanyUser":
            can_edit_value = (post_data.get("can_edit", "false") == "true")
            can_change_years_value = (post_data.get("can_change_years", "false") == "true")
            user.save()

            if hasattr(user, "companyuser"):
                user.companyuser.company_id = company_id
                user.companyuser.can_edit = can_edit_value
                user.companyuser.can_change_years = can_change_years_value
                user.companyuser.save()
            else:
                company = Company.objects.filter(id=company_id).first()
                CompanyUser.objects.create(user=user, company=company, can_edit=can_edit_value, can_change_years = can_change_years_value)
                

        # CompanyController
        elif role == "CompanyController":
            user.save()
            if hasattr(user, "companycontroller"):
                user.companycontroller.company_id = company_id
                user.companycontroller.save()
            else:
                company = Company.objects.filter(id=company_id).first()
                CompanyController.objects.create(user=user, company=company)

        # BusinessTeam
        elif role == "BusinessTeam":
            user.save()
            job_title = post_data.get("job_title")
            if job_title and hasattr(user, "businessanalysisteam"):
                user.businessanalysisteam.job_title = job_title
                user.businessanalysisteam.save()
                
        elif role == "CompanyFinanceManager":
            user.save()
            if hasattr(user, "companyfinancemanager"):
                user.companyfinancemanager.company_id = company_id
                user.companyfinancemanager.save()
            else:
                company = Company.objects.filter(id=company_id).first()
                CompanyFinanceManager.objects.create(user=user, company=company)

        # cleanup mismatch roles
        if role != "CompanyUser" and hasattr(user, "companyuser"):
            user.companyuser.delete()
            
        if role != "CompanyFinanceManager" and hasattr(user, "companyfinancemanager"):
            user.companyfinancemanager.delete()

        user.save()

    @staticmethod
    def _build_manage_users_context():
        role_order = {
            "Admin": 1,
            "Developer": 2,
            "BusinessTeam": 3,
            "CompanyUser": 4,
            "CompanyController": 5,
        }

        users = User.objects.prefetch_related(
            "companyuser__company",
            "companyfinancemanager__company",
            "businessanalysisteam",
        ).all()

        sorted_users = sorted(
            users,
            key=lambda u: (
                role_order.get(getattr(u, "role", ""), 99),
                u.companyuser.company.name if hasattr(u, "companyuser") and u.companyuser.company else "",
                (u.full_name or "").lower(),
            ),
        )

        companies = Company.objects.all()
        return {"users": sorted_users, "companies": companies}

    # ==================================================
    # IMPORT COMPANY USERS
    # ==================================================
    @staticmethod
    def import_company_users(*, actor, method, files, post_data):
        if method != "POST" or not files.get("csv_file"):
            return {"status": 400, "payload": {"message": "Invalid request"}}

        company_id = post_data.get("company_id")
        if not company_id:
            return {"status": 400, "payload": {"message": "Company ID is required."}}

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
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

            can_edit_raw = row.get("Can Edit", "False")
            can_edit_bool = str(can_edit_raw).lower() == "true"
            
            can_change_years_raw = row.get("Can Change Years", "False")
            can_change_years_bool = str(can_change_years_raw).lower() == "true"

            if not email or not full_name or not raw_password:
                skipped_count += 1
                continue

            # UPDATE
            existing = User.objects.filter(email=email).first()
            if existing:
                existing.full_name = full_name
                existing.password = make_password(raw_password)
                existing.save()

                if hasattr(existing, "companyuser"):
                    existing.companyuser.can_edit = can_edit_bool
                    existing.companyuser.can_change_years = can_change_years_bool
                    existing.companyuser.save()

                updated_count += 1
                continue

            # CREATE
            new_user = User.objects.create(
                email=email,
                full_name=full_name,
                password=make_password(raw_password),
                role="CompanyUser",
            )

            CompanyUser.objects.create(user=new_user, company=company, can_edit=can_edit_bool, can_change_years = can_change_years_bool)

            try:
                group = Group.objects.get(name="Client")
                new_user.groups.add(group)
            except Group.DoesNotExist:
                pass

            company.num_users += 1
            company.save(update_fields=["num_users"])

            created_count += 1

        return {
            "status": 200,
            "payload": {
                "message": f"Import completed. Created: {created_count}, Updated: {updated_count}, Skipped (invalid data): {skipped_count}"
            },
        }
