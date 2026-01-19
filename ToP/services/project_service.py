from django.shortcuts import get_object_or_404
from django.db import transaction
from django.core.exceptions import ValidationError

from ..models import (
    Project,
    ProjectConfiguration,
    Constraints,
    BaseNPV,
    GasPolicy,
    MaintenancePolicy,
    ProjectMasterplan,
    GasPolicyOffsets,
    MaintenancePolicyOffsets,
    MaintenancePolicyScheduling,
    ModificationRecords,
    Company,
    CTD,
    GasPolicyFees,
    Uploader,   # ✅ add this
)

from ..forms import (
    ProjectForm,
    ProjectConfigurationForm,
    ConstraintsForm,
    GasPolicyForm,
    MaintenancePolicyForm,
    ProjectMasterplanForm,
)


class ProjectManagementService:
    """
    Handles project creation, updating, and deletion.
    Adds uploader-company scoping:
      - If user has uploader_profile -> force company on create,
        only allow touching records under that company for update/delete.
      - Admin/Developer/TeamMember without uploader_profile -> normal behavior.
    """

    # ==================================================
    # SCOPE HELPERS
    # ==================================================

    @staticmethod
    def _get_uploader_company(user):
        """
        Returns Company if user has uploader_profile, else None.
        """
        try:
            return user.uploader_profile.company
        except (Uploader.DoesNotExist, AttributeError):
            return None

    @staticmethod
    def get_user_scope_flags(user):
        """
        Small helper for templates.
        """
        company = ProjectManagementService._get_uploader_company(user)
        return {
            "is_uploader": bool(company),
            "uploader_company_id": company.id if company else None,
            "uploader_company_name": company.name if company else None,
        }

    @staticmethod
    def get_projects_for_user(user):
        """
        Dashboard projects list scoped for uploader.
        """
        company = ProjectManagementService._get_uploader_company(user)
        if company:
            return Project.objects.filter(company=company)
        return Project.objects.all()

    @staticmethod
    def get_companies_for_user(user):
        """
        Dashboard companies dropdown scoped for uploader.
        """
        company = ProjectManagementService._get_uploader_company(user)
        if company:
            return Company.objects.filter(id=company.id)
        return Company.objects.all()

    @staticmethod
    def _inject_company_into_post_data(data, company):
        """
        Ensures POST data includes company for uploader users (even if UI hides/disabled it).
        """
        if not company:
            return data

        # QueryDict is immutable; copy it
        mutable = data.copy()
        current = mutable.get("company")
        if not current:
            mutable["company"] = str(company.id)
        return mutable

    @staticmethod
    def _project_scope_kwargs(user):
        """
        Returns kwargs to scope Project queries (for uploader users).
        """
        company = ProjectManagementService._get_uploader_company(user)
        return {"company": company} if company else {}

    # ==================================================
    # PUBLIC ENTRY POINTS
    # ==================================================

    @staticmethod
    def create_project(*, user, data, files=None):
        """
        Handles the entire project creation process.
        Excludes ProjectWebConfiguration creation.
        Forces company for uploader users.
        """
        uploader_company = ProjectManagementService._get_uploader_company(user)
        data = ProjectManagementService._inject_company_into_post_data(data, uploader_company)

        # 1. Validate All Forms
        forms_ctx = ProjectManagementService._validate_forms_for_create(data, files)
        if not forms_ctx["is_valid"]:
            return {"success": False, "errors": forms_ctx["errors"]}

        # 2. Create Project and Related Objects
        try:
            project = ProjectManagementService._perform_create_transaction(
                forms_ctx=forms_ctx,
                raw_data=data,
                uploader_company=uploader_company
            )
        except Exception as e:
            return {"success": False, "errors": {"__all__": [f"An error occurred during creation: {str(e)}"]}}

        # 3. Log Modification
        ModificationRecords.objects.create(
            user=user,
            type='CREATE',
            description=f'Created Project {project.name} related to {project.company}.'
        )

        return {"success": True, "project": project, "message": "Project and related configurations created successfully!"}

    @staticmethod
    def update_project(*, user, project_id, structured_data, files=None):
        """
        Handles project update.
        ✅ Scoped: uploader cannot update projects outside their company.
        """
        project = get_object_or_404(Project, id=project_id, **ProjectManagementService._project_scope_kwargs(user))

        try:
            ProjectManagementService._perform_update_transaction_direct(project, structured_data, files)
        except Exception as e:
            return {"success": False, "errors": {"__all__": [f"An error occurred during update: {str(e)}"]}}

        ModificationRecords.objects.create(
            user=user,
            type='UPDATE',
            description=f'Updated Project {project.name} related to {project.company}.'
        )

        return {"success": True, "project": project, "message": "Project updated successfully!"}

    @staticmethod
    def delete_project(*, user, project_id):
        """
        Deletes a project.
        ✅ Scoped: uploader cannot delete projects outside their company.
        """
        project = get_object_or_404(Project, id=project_id, **ProjectManagementService._project_scope_kwargs(user))

        try:
            project_name = project.name
            company_name = project.company.name
            project.delete()
        except Exception as e:
            return {"success": False, "errors": {"__all__": [f"An error occurred during deletion: {str(e)}"]}}

        ModificationRecords.objects.create(
            user=user,
            type='DELETE',
            description=f'Deleted Project {project_name} related to {company_name}.'
        )

        return {"success": True, "message": f"Project '{project_name}' and all related data deleted successfully."}

    @staticmethod
    def build_create_view_context(*, user, data=None, files=None):
        """
        Returns SAME forms + SAME context keys your view used.
        Adds flags to hide company selection in template for uploader users.
        """
        uploader_company = ProjectManagementService._get_uploader_company(user)
        scope_flags = ProjectManagementService.get_user_scope_flags(user)
        company = None
        
        if data is None:
            project_form = ProjectForm()
            config_form = ProjectConfigurationForm()
            constraints_form = ConstraintsForm()
            gas_policy_form = GasPolicyForm()
            maintenance_policy_form = MaintenancePolicyForm()
            masterplan_form = ProjectMasterplanForm()
        else:
            # ensure company exists for uploader even if UI hides it
            data = ProjectManagementService._inject_company_into_post_data(data, uploader_company)

            project_form = ProjectForm(data)
            config_form = ProjectConfigurationForm(data)
            constraints_form = ConstraintsForm(data)
            gas_policy_form = GasPolicyForm(data)
            maintenance_policy_form = MaintenancePolicyForm(data)
            masterplan_form = ProjectMasterplanForm(data, files)

        # If uploader: lock down company field (extra safety, even if template hides it)
        if uploader_company and "company" in project_form.fields:
            project_form.fields["company"].queryset = Company.objects.filter(id=uploader_company.id)
            project_form.fields["company"].initial = uploader_company.id
            project_form.fields["company"].disabled = True
            company = uploader_company

        return {
            "project_form": project_form,
            "config_form": config_form,
            "constraints_form": constraints_form,
            "gas_policy_form": gas_policy_form,
            "maintenance_policy_form": maintenance_policy_form,
            "masterplan_form": masterplan_form,
            "company":company,
            **scope_flags,
        }

    # ==================================================
    # DELETION ENTRY POINTS (SCOPED)
    # ==================================================

    @staticmethod
    def delete_npv(*, user, npv_id):
        try:
            company = ProjectManagementService._get_uploader_company(user)
            qs = BaseNPV.objects.select_related("project_config__project")
            if company:
                qs = qs.filter(project_config__project__company=company)
            npv = qs.get(id=npv_id)

            npv.delete()
            return {"success": True, "message": "NPV record deleted successfully!"}
        except BaseNPV.DoesNotExist:
            return {"success": False, "error": "NPV record not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_gas_fee(*, user, fee_id):
        try:
            company = ProjectManagementService._get_uploader_company(user)
            qs = GasPolicyFees.objects.select_related("gas_policy__project_config__project")
            if company:
                qs = qs.filter(gas_policy__project_config__project__company=company)
            fee = qs.get(id=fee_id)

            fee.delete()
            return {"success": True, "message": "Gas Policy Fee deleted successfully!"}
        except GasPolicyFees.DoesNotExist:
            return {"success": False, "error": "Gas Policy Fee not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_gas_offset(*, user, offset_id):
        try:
            company = ProjectManagementService._get_uploader_company(user)
            qs = GasPolicyOffsets.objects.select_related("gas_policy__project_config__project")
            if company:
                qs = qs.filter(gas_policy__project_config__project__company=company)
            offset = qs.get(id=offset_id)

            offset.delete()
            return {"success": True, "message": "Gas Policy Offset deleted successfully!"}
        except GasPolicyOffsets.DoesNotExist:
            return {"success": False, "error": "Gas Policy Offset not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_maintenance_offset(*, user, offset_id):
        try:
            company = ProjectManagementService._get_uploader_company(user)
            qs = MaintenancePolicyOffsets.objects.select_related("maintenance_policy__project_config__project")
            if company:
                qs = qs.filter(maintenance_policy__project_config__project__company=company)
            offset = qs.get(id=offset_id)

            offset.delete()
            return {"success": True, "message": "Maintenance Policy Offset deleted successfully!"}
        except MaintenancePolicyOffsets.DoesNotExist:
            return {"success": False, "error": "Maintenance Policy Offset not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_ctd(*, user, ctd_id):
        try:
            company = ProjectManagementService._get_uploader_company(user)
            qs = CTD.objects.select_related("project_constraints__project_config__project")
            if company:
                qs = qs.filter(project_constraints__project_config__project__company=company)
            ctd = qs.get(id=ctd_id)

            ctd.delete()
            return {"success": True, "message": "CTD Value deleted successfully!"}
        except CTD.DoesNotExist:
            return {"success": False, "error": "CTD Value not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_maintenance_schedule(*, user, schedule_id):
        try:
            company = ProjectManagementService._get_uploader_company(user)
            qs = MaintenancePolicyScheduling.objects.select_related("maintenance_policy__project_config__project")
            if company:
                qs = qs.filter(maintenance_policy__project_config__project__company=company)
            schedule = qs.get(id=schedule_id)

            schedule.delete()
            return {"success": True, "message": "Maintenance Schedule deleted successfully!"}
        except MaintenancePolicyScheduling.DoesNotExist:
            return {"success": False, "error": "Maintenance Schedule not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================================================
    # FORM VALIDATION HELPERS (For CREATE only)
    # ==================================================

    @staticmethod
    def _validate_forms_for_create(data, files):
        project_form = ProjectForm(data)
        config_form = ProjectConfigurationForm(data)
        constraints_form = ConstraintsForm(data)
        gas_policy_form = GasPolicyForm(data)
        maintenance_policy_form = MaintenancePolicyForm(data)

        masterplan_form = ProjectMasterplanForm(data, files) if files else None

        forms = [project_form, config_form, constraints_form, gas_policy_form, maintenance_policy_form]
        if masterplan_form:
            forms.append(masterplan_form)

        is_valid = all(form.is_valid() for form in forms)

        if is_valid:
            return {
                "is_valid": True,
                "project_form": project_form,
                "config_form": config_form,
                "constraints_form": constraints_form,
                "gas_policy_form": gas_policy_form,
                "maintenance_policy_form": maintenance_policy_form,
                "masterplan_form": masterplan_form
            }
        else:
            all_errors = {}
            for form in forms:
                all_errors.update(form.errors)
            print(f"DEBUG: Form validation failed for create. Errors: {all_errors}")
            return {"is_valid": False, "errors": all_errors}

    # ==================================================
    # TRANSACTIONAL HELPERS (For CREATE)
    # ==================================================

    @staticmethod
    def _perform_create_transaction(*, forms_ctx, raw_data, uploader_company=None):
        with transaction.atomic():
            # ✅ Save project with forced company for uploader
            project = forms_ctx["project_form"].save(commit=False)
            if uploader_company:
                project.company = uploader_company
            project.save()

            config = forms_ctx["config_form"].save(commit=False)
            config.project = project
            config.save()

            constraints = forms_ctx["constraints_form"].save(commit=False)
            constraints.project_config = config
            constraints.save()

            gas_policy = forms_ctx["gas_policy_form"].save(commit=False)
            gas_policy.project_config = config
            gas_policy.save()

            maintenance_policy = forms_ctx["maintenance_policy_form"].save(commit=False)
            maintenance_policy.project_config = config
            maintenance_policy.save()

            # Handle Base NPV
            ProjectManagementService._handle_base_npv(config, raw_data)

            # Handle CTD
            ProjectManagementService._handle_ctd(constraints, raw_data)

            # Handle Masterplan
            if forms_ctx["masterplan_form"] and forms_ctx["masterplan_form"].cleaned_data.get("image"):
                masterplan = forms_ctx["masterplan_form"].save(commit=False)
                masterplan.project = project
                masterplan.save()

            # Handle related policy data
            ProjectManagementService._handle_related_policy_data(gas_policy, maintenance_policy, raw_data)

        return project

    # ==================================================
    # TRANSACTIONAL HELPERS (For UPDATE - Direct)
    # ==================================================

    @staticmethod
    def _perform_update_transaction_direct(project, structured_data, files):
        """Performs the database transaction for project update using structured JSON data."""
        with transaction.atomic():
            # ✅ Update Project
            project.description = structured_data["project"].get("description", project.description)
            project.save()

            # ✅ Handle Masterplan Upload (if files provided)
            if files and 'masterplan_image' in files:
                masterplan_image = files['masterplan_image']
                # Validate file type (example)
                allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                if masterplan_image.content_type not in allowed_types:
                    raise ValidationError("Invalid file type for masterplan.")
                # Validate file size (example)
                if masterplan_image.size > 100 * 1024 * 1024: # 100 MB
                    raise ValidationError("File too large for masterplan.")

                masterplan, created = ProjectMasterplan.objects.get_or_create(project=project)
                if masterplan.image:
                    masterplan.image.delete(save=False)
                masterplan.image = masterplan_image
                masterplan.save()

            # ✅ Update or Create Project Configuration
            config, _ = ProjectConfiguration.objects.get_or_create(project=project)
            config.interest_rate = float(structured_data["project_config"].get("interest_rate", config.interest_rate)) / 100
            config.base_dp = float(structured_data["project_config"].get("base_dp", config.base_dp)) / 100
            config.base_tenor_years = structured_data["project_config"].get("base_tenor_years", config.base_tenor_years)
            config.max_tenor_years = structured_data["project_config"].get("max_tenor_years", config.max_tenor_years)
            config.base_payment_frequency = structured_data["project_config"].get("payment_frequency", config.base_payment_frequency)
            config.default_scheme = structured_data["project_config"].get("default_scheme", config.default_scheme)
            config.use_static_base_npv = structured_data["project_config"].get("use_static_base_npv", config.use_static_base_npv)
            config.maximum_requests_per_sales = structured_data["project_config"].get("maximum_requests_per_sales", config.maximum_requests_per_sales)
            config.save()

            # ✅ Update or Create Constraints
            constraints, _ = Constraints.objects.get_or_create(project_config=config)
            constraints.dp_min = float(structured_data["constraints"].get("dp_min", constraints.dp_min)) / 100
            constraints.max_discount = float(structured_data["constraints"].get("max_discount", constraints.max_discount)) / 100
            constraints.max_exception_discount = float(structured_data["constraints"].get("max_exception_discount", constraints.max_exception_discount)) / 100
            constraints.save()

            # ✅ Update or Create Gas Policy
            gas_policy, _ = GasPolicy.objects.get_or_create(project_config=config)
            gas_policy.is_applied = structured_data["gas_policy"].get("is_applied", gas_policy.is_applied)

            # --- CRITICAL FIX: Handle potentially null/empty string values ---
            gas_num_pmts_raw = structured_data["gas_policy"].get("gas_num_pmts", gas_policy.gas_num_pmts)
            if gas_num_pmts_raw is None or gas_num_pmts_raw == "": # Check for null or empty string
                # Use the existing value from the database if the new value is null/empty
                gas_policy.gas_num_pmts = gas_policy.gas_num_pmts
            else:
                # Otherwise, use the new value from the data
                gas_policy.gas_num_pmts = gas_num_pmts_raw # Or convert if necessary, e.g., int(gas_num_pmts_raw)

            gas_policy.scheduling = structured_data["gas_policy"].get("scheduling", gas_policy.scheduling)
            gas_policy.save()

            # ✅ Update or Create Maintenance Policy
            maintenance_policy, _ = MaintenancePolicy.objects.get_or_create(project_config=config)
            maintenance_policy.is_applied = structured_data["maintenance_policy"].get("is_applied", maintenance_policy.is_applied)
            maintenance_policy.split_two_one_on_delivery = structured_data["maintenance_policy"].get("split_two_one_on_delivery", maintenance_policy.split_two_one_on_delivery)

            # --- CRITICAL FIX: Handle potentially null/empty string values ---
            maintenance_num_pmts_raw = structured_data["maintenance_policy"].get("maintenance_num_pmts", maintenance_policy.maintenance_num_pmts)
            if maintenance_num_pmts_raw is None or maintenance_num_pmts_raw == "": # Check for null or empty string
                # Use the existing value from the database if the new value is null/empty
                maintenance_policy.maintenance_num_pmts = maintenance_policy.maintenance_num_pmts
            else:
                # Otherwise, use the new value from the data
                maintenance_policy.maintenance_num_pmts = maintenance_num_pmts_raw # Or convert if necessary, e.g., int(maintenance_num_pmts_raw)

            maintenance_policy.save()

            # ✅ Update Base NPV
            BaseNPV.objects.filter(project_config=config).delete() # Clear old
            for npv in structured_data.get("base_npv", []):
                term_period = npv.get("term_period")
                npv_value = npv.get("npv_value")
                if term_period == "0" and npv_value == "0":
                    continue
                if term_period is not None and npv_value is not None:
                    BaseNPV.objects.create(
                        project_config=config,
                        term_period=term_period,
                        npv_value=float(npv_value) / 100
                    )

            # ✅ Update Gas Policy Fees/Offsets (if GasPolicyFees model exists and is used)
            # gas_policy_fees_data = structured_data.get("gas_policy_fees", [])
            # for fee in gas_policy_fees_data:
            #     # Similar logic to create/update GasPolicyFees
            #     pass

            # ✅ Update Gas Policy Offsets
            GasPolicyOffsets.objects.filter(gas_policy=gas_policy).delete() # Clear old
            for offset in structured_data.get("gas_policy_offsets", []):
                term_period = offset.get("term_period")
                offset_value = offset.get("offset_value")
                if term_period == "0" and offset_value == "0":
                    continue
                if term_period is not None and offset_value is not None:
                    GasPolicyOffsets.objects.create(
                        gas_policy=gas_policy,
                        term_period=term_period,
                        offset_value=offset_value
                    )

            # ✅ Update CTD Records
            CTD.objects.filter(project_constraints=constraints).delete() # Clear old
            for ctd in structured_data.get("ctd_values", []):
                term_period = ctd.get("term_period")
                npv_value = ctd.get("npv_value")
                if term_period == "0" and npv_value == "0":
                    continue
                if term_period is not None and npv_value is not None:
                    CTD.objects.create(
                        project_constraints=constraints,
                        term_period=term_period,
                        npv_value=float(npv_value) / 100
                    )

            # ✅ Update Maintenance Policy Scheduling/Offsets
            MaintenancePolicyScheduling.objects.filter(maintenance_policy=maintenance_policy).delete() # Clear old
            MaintenancePolicyOffsets.objects.filter(maintenance_policy=maintenance_policy).delete() # Clear old
            for schedule in structured_data.get("maintenance_scheduling", []):
                term_period = schedule.get("term_period")
                amount = schedule.get("amount")
                if term_period == "0" and amount == "0":
                    continue
                if term_period is not None and amount is not None:
                    MaintenancePolicyScheduling.objects.create(
                        maintenance_policy=maintenance_policy,
                        term_period=term_period,
                        scheduling=amount
                    )

            for offset in structured_data.get("maintenance_policy_offsets", []):
                term_period = offset.get("term_period")
                offset_value = offset.get("offset_value")
                if term_period == "0" and offset_value == "0":
                    continue
                if term_period is not None and offset_value is not None:
                    MaintenancePolicyOffsets.objects.create(
                        maintenance_policy=maintenance_policy,
                        term_period=term_period,
                        offset_value=offset_value
                    )

    # ==================================================
    # DATA HANDLING HELPERS (For CREATE only) - unchanged
    # ==================================================

    @staticmethod
    def _handle_base_npv(config, raw_data, clear_existing=False):
        if clear_existing:
            BaseNPV.objects.filter(project_config=config).delete()

        term_periods = raw_data.getlist('term_period')
        npv_values = raw_data.getlist('npv_value')

        for term_period, npv_value in zip(term_periods, npv_values):
            if term_period.strip() and npv_value.strip():
                BaseNPV.objects.create(
                    project_config=config,
                    term_period=term_period,
                    npv_value=(float(npv_value) / 100)
                )

    @staticmethod
    def _handle_ctd(constraints, raw_data, clear_existing=False):
        if clear_existing:
            CTD.objects.filter(project_constraints=constraints).delete()

        ctd_term_periods = raw_data.getlist('ctd_term_period')
        ctd_npv_values = raw_data.getlist('ctd_npv_value')

        for ctd_term_period, ctd_npv_value in zip(ctd_term_periods, ctd_npv_values):
            if ctd_term_period.strip() and ctd_npv_value.strip():
                CTD.objects.create(
                    project_constraints=constraints,
                    term_period=ctd_term_period,
                    npv_value=(float(ctd_npv_value) / 100)
                )

    @staticmethod
    def _handle_related_policy_data(gas_policy, maintenance_policy, raw_data, clear_existing=False):
        if clear_existing:
            GasPolicyOffsets.objects.filter(gas_policy=gas_policy).delete()
            MaintenancePolicyOffsets.objects.filter(maintenance_policy=maintenance_policy).delete()
            MaintenancePolicyScheduling.objects.filter(maintenance_policy=maintenance_policy).delete()

        gas_offset_periods = raw_data.getlist('gas_offset_period')
        gas_policy_offsets = raw_data.getlist('gas_policy_offsets')
        for term_period, offset_value in zip(gas_offset_periods, gas_policy_offsets):
            if term_period.strip() and offset_value.strip():
                GasPolicyOffsets.objects.create(
                    gas_policy=gas_policy,
                    term_period=term_period,
                    offset_value=offset_value
                )

        maintenance_offset_periods = raw_data.getlist('maintenance_offset_period')
        maintenance_policy_offsets = raw_data.getlist('maintenance_policy_offsets')
        for term_period, offset_value in zip(maintenance_offset_periods, maintenance_policy_offsets):
            if term_period.strip() and offset_value.strip():
                MaintenancePolicyOffsets.objects.create(
                    maintenance_policy=maintenance_policy,
                    term_period=term_period,
                    offset_value=offset_value
                )

        maintenance_scheduling_periods = raw_data.getlist('maintenance_scheduling_period')
        maintenance_scheduling_data = raw_data.getlist('maintenance_policy_scheduling')
        for term_period, scheduling_value in zip(maintenance_scheduling_periods, maintenance_scheduling_data):
            if term_period.strip() and scheduling_value.strip():
                MaintenancePolicyScheduling.objects.create(
                    maintenance_policy=maintenance_policy,
                    term_period=term_period,
                    scheduling=scheduling_value
                )

    @staticmethod
    def remove_masterplan(*, user, project_id):
        """
        Scoped: uploader can only remove masterplan from their own company’s projects.
        """
        try:
            project = get_object_or_404(Project, id=project_id, **ProjectManagementService._project_scope_kwargs(user))

            try:
                masterplan = project.masterplan
                if masterplan and masterplan.image:
                    masterplan.image.delete(save=False)
                    masterplan.delete()

                    ModificationRecords.objects.create(
                        user=user,
                        type='UPDATE',
                        description=f'Removed masterplan from Project {project.name}.'
                    )

                    return {"success": True, "message": "Masterplan removed successfully!"}
                else:
                    return {"success": False, "error": "No masterplan found"}
            except ProjectMasterplan.DoesNotExist:
                return {"success": False, "error": "No masterplan found"}

        except Exception as e:
            return {"success": False, "error": str(e)}
