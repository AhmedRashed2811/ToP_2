# services.py (append this class - Updated with deletion methods)

from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import QueryDict # Import QueryDict

from ..models import (
    Project,
    ProjectConfiguration,
    Constraints,
    # ProjectWebConfiguration, # <-- Removed from import
    BaseNPV,
    GasPolicy,
    MaintenancePolicy,
    ProjectMasterplan,
    GasPolicyOffsets,
    MaintenancePolicyOffsets,
    MaintenancePolicyScheduling,
    ModificationRecords,
    Company,
    CTD, # <-- Add CTD import
    # Add other related models if needed like GasPolicyFees if used in the old view
    GasPolicyFees, # Example if used
)

from ..forms import ( # Assuming you have these forms in forms.py
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
    Phase 3 – Step 5: Refactor project CRUD operations into a service.
    Logic and behavior are unchanged.
    Excludes ProjectWebConfiguration creation/update during project CRUD.
    Handles multi-value fields (like Base NPV, CTD, Offsets) using raw data.getlist().
    Handles structured JSON data for updates directly (no forms for update).
    """

    # ==================================================
    # PUBLIC ENTRY POINTS
    # ==================================================

    @staticmethod
    def create_project(*, user, data, files=None):
        """
        Handles the entire project creation process.
        Excludes ProjectWebConfiguration creation.
        Handles multi-value fields using raw data.getlist().
        Uses Django Forms for validation and creation.
        """
        # 1. Validate All Forms
        forms_ctx = ProjectManagementService._validate_forms_for_create(data, files)
        if not forms_ctx["is_valid"]:
            # Return detailed errors from the forms
            return {"success": False, "errors": forms_ctx["errors"]}

        # 2. Create Project and Related Objects (excluding ProjectWebConfiguration)
        try:
            project = ProjectManagementService._perform_create_transaction(forms_ctx, data) # Pass raw data
        except Exception as e:
            # Include the exception details in the error message
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
        Handles the entire project update process.
        Excludes ProjectWebConfiguration update here; handled separately.
        Expects structured JSON data like {"project": {...}, "project_config": {...}, ...}.
        Does NOT use Django Forms for validation/update. Mimics old view logic.
        """
        project = get_object_or_404(Project, id=project_id)

        try:
            # Perform the update transaction using structured data
            ProjectManagementService._perform_update_transaction_direct(project, structured_data, files)
        except Exception as e:
            # Include the exception details in the error message
            return {"success": False, "errors": {"__all__": [f"An error occurred during update: {str(e)}"]}}

        # Log Modification
        ModificationRecords.objects.create(
            user=user,
            type='UPDATE',
            description=f'Updated Project {project.name} related to {project.company}.'
        )

        return {"success": True, "project": project, "message": "Project updated successfully!"}


    @staticmethod
    def delete_project(*, user, project_id):
        """
        Handles the entire project deletion process.
        ProjectWebConfiguration deletion happens via CASCADE if linked to Project.
        """
        project = get_object_or_404(Project, id=project_id)

        try:
            project_name = project.name
            company_name = project.company.name
            project.delete() # Django handles cascading deletes based on models
        except Exception as e:
            # Include the exception details in the error message
            return {"success": False, "errors": {"__all__": [f"An error occurred during deletion: {str(e)}"]}}

        # Log Modification
        ModificationRecords.objects.create(
            user=user,
            type='DELETE',
            description=f'Deleted Project {project_name} related to {company_name}.'
        )

        return {"success": True, "message": f"Project '{project_name}' and all related data deleted successfully."}

    @staticmethod
    def build_create_view_context(*, data=None, files=None):
        """
        Returns the SAME forms + SAME context keys your view used.
        Used to re-render the create_project page (GET or failed POST).

        - data: request.POST (QueryDict) or None
        - files: request.FILES (MultiValueDict) or None
        """
        if data is None:
            # GET: empty forms
            project_form = ProjectForm()
            config_form = ProjectConfigurationForm()
            constraints_form = ConstraintsForm()
            gas_policy_form = GasPolicyForm()
            maintenance_policy_form = MaintenancePolicyForm()
            masterplan_form = ProjectMasterplanForm()
        else:
            # POST: bound forms (exactly like your view)
            project_form = ProjectForm(data)
            config_form = ProjectConfigurationForm(data)
            constraints_form = ConstraintsForm(data)
            gas_policy_form = GasPolicyForm(data)
            maintenance_policy_form = MaintenancePolicyForm(data)
            masterplan_form = ProjectMasterplanForm(data, files)  # include files if needed

        return {
            "project_form": project_form,
            "config_form": config_form,
            "constraints_form": constraints_form,
            "gas_policy_form": gas_policy_form,
            "maintenance_policy_form": maintenance_policy_form,
            "masterplan_form": masterplan_form,
        }

    # ==================================================
    # DELETION ENTRY POINTS
    # ==================================================

    @staticmethod
    def delete_npv(*, user, npv_id):
        """
        Handles deletion of a BaseNPV record.
        """
        try:
            npv = BaseNPV.objects.get(id=npv_id)
            npv.delete()
            return {"success": True, "message": "NPV record deleted successfully!"}
        except BaseNPV.DoesNotExist:
            return {"success": False, "error": "NPV record not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_gas_fee(*, user, fee_id):
        """
        Handles deletion of a GasPolicyFees record.
        """
        try:
            fee = GasPolicyFees.objects.get(id=fee_id)
            fee.delete()
            return {"success": True, "message": "Gas Policy Fee deleted successfully!"}
        except GasPolicyFees.DoesNotExist:
            return {"success": False, "error": "Gas Policy Fee not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_gas_offset(*, user, offset_id):
        """
        Handles deletion of a GasPolicyOffsets record.
        """
        try:
            offset = GasPolicyOffsets.objects.get(id=offset_id)
            offset.delete()
            return {"success": True, "message": "Gas Policy Offset deleted successfully!"}
        except GasPolicyOffsets.DoesNotExist:
            return {"success": False, "error": "Gas Policy Offset not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_maintenance_offset(*, user, offset_id):
        """
        Handles deletion of a MaintenancePolicyOffsets record.
        """
        try:
            # Note: The original view had GasPolicyOffsets.DoesNotExist for this,
            # which seems like a bug. Corrected to MaintenancePolicyOffsets.DoesNotExist.
            offset = MaintenancePolicyOffsets.objects.get(id=offset_id)
            offset.delete()
            return {"success": True, "message": "Maintenance Policy Offset deleted successfully!"}
        except MaintenancePolicyOffsets.DoesNotExist:
            return {"success": False, "error": "Maintenance Policy Offset not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_ctd(*, user, ctd_id):
        """
        Handles deletion of a CTD record.
        """
        try:
            ctd = CTD.objects.get(id=ctd_id)
            ctd.delete()
            return {"success": True, "message": "CTD Value deleted successfully!"}
        except CTD.DoesNotExist:
            return {"success": False, "error": "CTD Value not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_maintenance_schedule(*, user, schedule_id):
        """
        Handles deletion of a MaintenancePolicyScheduling record.
        """
        try:
            schedule = MaintenancePolicyScheduling.objects.get(id=schedule_id)
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
        """Validates all forms required for project creation."""
        project_form = ProjectForm(data)
        config_form = ProjectConfigurationForm(data)
        constraints_form = ConstraintsForm(data)
        gas_policy_form = GasPolicyForm(data)
        maintenance_policy_form = MaintenancePolicyForm(data)
        masterplan_form = ProjectMasterplanForm(files or {}) if files else None

        forms = [project_form, config_form, constraints_form, gas_policy_form, maintenance_policy_form]
        if masterplan_form:
            forms.append(masterplan_form)

        # Check if all forms are valid
        is_valid = all(form.is_valid() for form in forms)

        if is_valid:
            # All forms are valid
            return {"is_valid": True, "project_form": project_form, "config_form": config_form,
                    "constraints_form": constraints_form, "gas_policy_form": gas_policy_form,
                    "maintenance_policy_form": maintenance_policy_form, "masterplan_form": masterplan_form}
        else:
            # Forms are invalid, collect all errors
            all_errors = {}
            for form in forms:
                # form.errors is a dictionary like {'field_name': ['error_message1', 'error_message2'], ...}
                all_errors.update(form.errors)
            print(f"DEBUG: Form validation failed for create. Errors: {all_errors}") # Debug print
            return {"is_valid": False, "errors": all_errors}


    # ==================================================
    # TRANSACTIONAL HELPERS (For CREATE)
    # ==================================================

    @staticmethod
    def _perform_create_transaction(forms_ctx, raw_data): # Added raw_data parameter
        """Performs the database transaction for project creation."""
        with transaction.atomic():
            project = forms_ctx["project_form"].save()

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

            # Handle Base NPV - Use raw_data.getlist()
            ProjectManagementService._handle_base_npv(config, raw_data)

            # Handle CTD - Use raw_data.getlist()
            ProjectManagementService._handle_ctd(constraints, raw_data)

            # Handle Masterplan
            if forms_ctx["masterplan_form"] and forms_ctx["masterplan_form"].cleaned_data.get("image"):
                masterplan = forms_ctx["masterplan_form"].save(commit=False)
                masterplan.project = project
                masterplan.save()

            # Handle related policy data (Offsets, Scheduling) - Use raw_data.getlist()
            ProjectManagementService._handle_related_policy_data(gas_policy, maintenance_policy, raw_data)

            # ProjectWebConfiguration is NOT created here.
            # It should be created/updated separately, e.g., via project_web_config view.

        return project


    # ==================================================
    # TRANSACTIONAL HELPERS (For UPDATE - Direct Model Manipulation)
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
            config.days_until_unblocking = structured_data["project_config"].get("days_until_unblocking", config.days_until_unblocking)
            config.variable_delivery_date = structured_data["project_config"].get("variable_delivery_date", config.variable_delivery_date)
            config.base_payment_frequency = structured_data["project_config"].get("payment_frequency", config.base_payment_frequency)
            config.default_scheme = structured_data["project_config"].get("default_scheme", config.default_scheme)
            config.use_static_base_npv = structured_data["project_config"].get("use_static_base_npv", config.use_static_base_npv)
            config.maximum_requests_per_sales = structured_data["project_config"].get("maximum_requests_per_sales", config.maximum_requests_per_sales)
            config.save()

            # ✅ Update or Create Constraints
            constraints, _ = Constraints.objects.get_or_create(project_config=config)
            constraints.dp_min = float(structured_data["constraints"].get("dp_min", constraints.dp_min)) / 100
            constraints.dp_plus_first_pmt = float(structured_data["constraints"].get("dp_plus_first_pmt", constraints.dp_plus_first_pmt)) / 100
            constraints.dp_plus_first_plus_second_pmt = float(structured_data["constraints"].get("dp_plus_first_plus_second_pmt", constraints.dp_plus_first_plus_second_pmt)) / 100
            constraints.dp_plus_first_plus_second_plus_third_pmt = float(structured_data["constraints"].get("dp_plus_first_plus_second_plus_third_pmt", constraints.dp_plus_first_plus_second_plus_third_pmt)) / 100
            constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt = float(structured_data["constraints"].get("dp_plus_first_plus_second_plus_third_plus_forth_pmt", constraints.dp_plus_first_plus_second_plus_third_plus_forth_pmt)) / 100
            constraints.first_year_min = float(structured_data["constraints"].get("first_year_min", constraints.first_year_min)) / 100
            constraints.annual_min = float(structured_data["constraints"].get("annual_min", constraints.annual_min)) / 100
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
    # DATA HANDLING HELPERS (For CREATE only)
    # ==================================================

    @staticmethod
    def _handle_base_npv(config, raw_data, clear_existing=False):
        """Handles creation/deletion of BaseNPV records for CREATE using raw_data.getlist()."""
        if clear_existing:
            BaseNPV.objects.filter(project_config=config).delete()

        # Use raw_data (QueryDict) to get lists
        term_periods = raw_data.getlist('term_period') # Adjust key as needed
        npv_values = raw_data.getlist('npv_value')    # Adjust key as needed

        for term_period, npv_value in zip(term_periods, npv_values):
            if term_period.strip() and npv_value.strip():
                BaseNPV.objects.create(
                    project_config=config,
                    term_period=term_period,
                    npv_value=(float(npv_value) / 100) # Assuming input is percentage, convert to decimal
                )

    @staticmethod
    def _handle_ctd(constraints, raw_data, clear_existing=False):
        """Handles creation/deletion of CTD records for CREATE using raw_data.getlist()."""
        if clear_existing:
            CTD.objects.filter(project_constraints=constraints).delete()

        # Use raw_data (QueryDict) to get lists
        ctd_term_periods = raw_data.getlist('ctd_term_period') # Adjust key as needed
        ctd_npv_values = raw_data.getlist('ctd_npv_value')    # Adjust key as needed

        for ctd_term_period, ctd_npv_value in zip(ctd_term_periods, ctd_npv_values):
            if ctd_term_period.strip() and ctd_npv_value.strip():
                CTD.objects.create(
                    project_constraints=constraints,
                    term_period=ctd_term_period,
                    npv_value=(float(ctd_npv_value) / 100) # Assuming input is percentage, convert to decimal
                )

    @staticmethod
    def _handle_related_policy_data(gas_policy, maintenance_policy, raw_data, clear_existing=False):
        """Handles creation/deletion of related policy offset and scheduling records for CREATE using raw_data.getlist()."""
        if clear_existing:
            GasPolicyOffsets.objects.filter(gas_policy=gas_policy).delete()
            MaintenancePolicyOffsets.objects.filter(maintenance_policy=maintenance_policy).delete()
            MaintenancePolicyScheduling.objects.filter(maintenance_policy=maintenance_policy).delete()

        # Handle Gas Policy Offsets - Use raw_data.getlist()
        gas_offset_periods = raw_data.getlist('gas_offset_period') # Adjust key as needed
        gas_policy_offsets = raw_data.getlist('gas_policy_offsets') # Adjust key as needed
        for term_period, offset_value in zip(gas_offset_periods, gas_policy_offsets):
            if term_period.strip() and offset_value.strip():
                GasPolicyOffsets.objects.create(
                    gas_policy=gas_policy,
                    term_period=term_period,
                    offset_value=offset_value
                )

        # Handle Maintenance Policy Offsets - Use raw_data.getlist()
        maintenance_offset_periods = raw_data.getlist('maintenance_offset_period') # Adjust key as needed
        maintenance_policy_offsets = raw_data.getlist('maintenance_policy_offsets') # Adjust key as needed
        for term_period, offset_value in zip(maintenance_offset_periods, maintenance_policy_offsets):
            if term_period.strip() and offset_value.strip():
                MaintenancePolicyOffsets.objects.create(
                    maintenance_policy=maintenance_policy,
                    term_period=term_period,
                    offset_value=offset_value
                )

        # Handle Maintenance Policy Scheduling - Use raw_data.getlist()
        maintenance_scheduling_periods = raw_data.getlist('maintenance_scheduling_period') # Adjust key as needed
        maintenance_scheduling_data = raw_data.getlist('maintenance_policy_scheduling') # Adjust key as needed
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
        Handles removal of a project's masterplan image and record.
        """
        try:
            project = Project.objects.get(id=project_id)
            try:
                masterplan = project.masterplan
                if masterplan and masterplan.image:
                    # Delete the image file
                    masterplan.image.delete(save=False)
                    # Delete the masterplan record
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

        except Project.DoesNotExist:
            return {"success": False, "error": "Project not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}