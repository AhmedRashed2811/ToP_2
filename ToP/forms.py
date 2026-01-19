from django import forms
from .models import *
from django.contrib.auth.models import Group
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import ValidationError
import re


# forms.py
from django import forms
from .models import Company, CompanyType

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            "name",
            "comp_type",
            "joining_date",
            "is_active",
            "erp_url", "erp_url_key",
            "erp_hold_url", "erp_hold_url_key",
            "erp_approve_url", "erp_approve_url_key",
            "erp_url_leads", "erp_url_leads_key",
            "google_sheet_url", "google_sheet_gid", "google_sheet_title",
            "logo",
        ]
        widgets = {
            "joining_date": forms.DateInput(attrs={"type": "date"}),
            "comp_type": forms.CheckboxSelectMultiple(choices=CompanyType.choices),        
            
        }

    def clean(self):
        cleaned = super().clean()
        # 'types' will now be a list, e.g., ['erp', 'google_sheets']
        types = cleaned.get("comp_type") or []

        # 2. Validate ERP fields if 'erp' is IN the selected types
        if CompanyType.ERP in types:
            if not cleaned.get("erp_url"):
                self.add_error("erp_url", "ERP URL is required when ERP module is selected.")
        
        # 3. Validate Sheet fields if 'google_sheets' is IN the selected types
        if CompanyType.GOOGLE_SHEETS in types:
            if not cleaned.get("google_sheet_url"):
                self.add_error("google_sheet_url", "Google Sheet URL is required when Google Sheets module is selected.")

        # 4. REMOVED the logic that clears/nones the other fields. 
        # We want to keep them if the user filled them out.

        return cleaned






# class ProjectForm(forms.ModelForm):
#     class Meta:
#         model = Project
#         fields = ['company', 'name', 'description']

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['company', 'name', 'description']
        labels = {
                'name': 'Project Name',  # 👈 Change label here
            }
    # # Add a custom field for the project name
    # name = forms.ChoiceField(choices=[], required=True)

    # def __init__(self, *args, **kwargs):
    #     super(ProjectForm, self).__init__(*args, **kwargs)

    #     # Dynamically populate the choices for the project name field
    #     if 'company' in self.data:
    #         try:
    #             company_id = int(self.data.get('company'))
    #             company = Company.objects.get(id=company_id)

    #             # Get all unique project names from the Unit model for the selected company
    #             unit_project_names = set(
    #                 Unit.objects.filter(company=company).values_list('project', flat=True).distinct()
    #             )

    #             # Get all existing project names from the Project model for the selected company
    #             existing_project_names = set(
    #                 Project.objects.filter(company=company).values_list('name', flat=True)
    #             )

    #             # Exclude existing project names from the dropdown choices
    #             available_project_names = unit_project_names - existing_project_names

    #             # Populate the choices for the dropdown
    #             self.fields['name'].choices = [
    #                 (project_name, project_name)
    #                 for project_name in available_project_names
    #             ]
    #         except (ValueError, Company.DoesNotExist):
    #             # If no valid company is selected, clear the choices
    #             self.fields['name'].choices = []


class ProjectConfigurationForm(forms.ModelForm):
    class Meta:
        model = ProjectConfiguration
        fields = [
            'interest_rate',
            'base_dp',
            'base_tenor_years',
            'max_tenor_years',
            'base_payment_frequency',
            'default_scheme',                 # ✅ ensure default_scheme is included
            'use_static_base_npv',
            'maximum_requests_per_sales',     # ✅ NEW FIELD
        ]
        labels = {
            'base_dp': 'Down Payment',
            'max_tenor_years': "Maximum Tenor Years",
            'maximum_requests_per_sales': 'Max Requests per Sales',
        }

    # Dropdowns
    base_payment_frequency = forms.ChoiceField(
        choices=[
            ('', 'Select Payment'),
            ('monthly', ' Monthly'),
            ('quarterly', 'Quarterly'),
            ('semi-annual', 'Semi-Annual'),
            ('annually', 'Annually')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    default_scheme = forms.ChoiceField(
        choices=[
            ('', 'Select Scheme'),
            ('Flat', 'Flat'),
            ('FlatBackLoaded', 'Flat Back Loaded'),
            ('Bullet', 'Bullet'),
            ('BulletBackloaded', 'Bullet Back Loaded'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # Normalizations
    def clean_interest_rate(self):
        rate = self.cleaned_data.get('interest_rate')
        return rate / 100 if rate is not None else None

    def clean_base_dp(self):
        dp = self.cleaned_data.get('base_dp')
        return dp / 100 if dp is not None else None

    # Validation for the new field (optional but recommended)
    def clean_maximum_requests_per_sales(self):
        val = self.cleaned_data.get('maximum_requests_per_sales')
        if val is not None and val == 0:
            raise forms.ValidationError("Max Requests per Sales must be greater than 0 or left blank.")
        return val

    

class ConstraintsForm(forms.ModelForm):
    class Meta:
        model = Constraints
        fields = ['dp_min', 'max_discount','max_exception_discount']

        labels = {
                'dp_min': 'Minimum DP',  # 👈 Change label here
                'max_discount': 'Maximum Discount',  # 👈 Change label here
                'max_exception_discount': 'Maximum Exception Disc.',  # 👈 Change label here
            }

    def clean(self):
        cleaned_data = super().clean()
        fields_to_divide = ['dp_min', 'max_discount','max_exception_discount']

        for field in fields_to_divide:
            value = cleaned_data.get(field)
            if value is not None:
                cleaned_data[field] = value / 100

        return cleaned_data
    

class BaseNPVForm(forms.ModelForm):
    class Meta:
        model = BaseNPV
        fields = ['term_period', 'npv_value']

    def clean_npv_value(self):
        npv = self.cleaned_data.get('npv_value')
        return npv / 100 if npv is not None else None

class CTDForm(forms.ModelForm):
    class Meta:
        model = BaseNPV
        fields = ['term_period', 'npv_value']
    
    def clean_npv_value(self):
        npv = self.cleaned_data.get('npv_value')
        return npv / 100 if npv is not None else None


# class GasPolicyForm(forms.ModelForm):
#     class Meta:
#         model = GasPolicy
#         fields = ['is_applied', 'num_pmts', 'scheduling']

# class MaintenancePolicyForm(forms.ModelForm):
#     class Meta:
#         model = MaintenancePolicy
#         fields = ['is_applied', 'num_pmts']


class GasPolicyForm(forms.ModelForm):
    is_applied_gas = forms.BooleanField(
        label="Apply Gas Policy",
        required=False
    )

    SCHEDULING_CHOICES = [
        ('', '---Select---'),
        ('at_delivery', 'At Delivery'),
        ('before_delivery', 'Before Delivery'),
    ]

    scheduling = forms.ChoiceField(
        choices=SCHEDULING_CHOICES,
        required=False,  # ✅ Make it optional
        widget=forms.Select(attrs={'class': 'form-control'})
    )


    class Meta:
        model = GasPolicy
        fields = ['is_applied_gas', 'scheduling','gas_num_pmts']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Map the renamed field to the original model field
        self.fields['is_applied_gas'].initial = self.instance.is_applied

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.is_applied = self.cleaned_data['is_applied_gas']
        if commit:
            instance.save()
        return instance


class MaintenancePolicyForm(forms.ModelForm):
    is_applied_maintenance = forms.BooleanField(
        label="Apply Maintenance Policy",
        required=False
    )

    class Meta:
        model = MaintenancePolicy
        fields = ['is_applied_maintenance', 'maintenance_num_pmts', 'split_two_one_on_delivery']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Map the renamed field to the original model field
        self.fields['is_applied_maintenance'].initial = self.instance.is_applied

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.is_applied = self.cleaned_data['is_applied_maintenance']
        if commit:
            instance.save()
        return instance


from django import forms
from django.utils.timezone import now

from .models import (
    User,
    Company,
    SalesTeam,
)

class CreateUserForm(forms.ModelForm):
    # Auth password fields (kept)
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=True,
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=True,
    )

    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('CompanyAdmin', 'Company Admin'),
        ('Manager', 'Manager'),
        ('SalesHead', 'Sales Head'),
        ('Sales', 'Sales'),
        ('SalesOperation', 'Sales Operation'),
        ('Uploader', 'Uploader'),
        ('Viewer', 'Viewer'),
        ('BusinessTeam', 'Business Team'),
    ]
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={'autocomplete': 'off', 'id': 'id_role'})
    )

    # Company (required for company roles)
    company = forms.ModelChoiceField(
        queryset=Company.objects.all().order_by("name"),
        required=False,
        widget=forms.Select(attrs={'autocomplete': 'off', 'id': 'id_company'})
    )

    # Team (only for Sales & SalesHead)
    team = forms.ModelChoiceField(
        queryset=SalesTeam.objects.select_related("company").all().order_by("company__name", "name"),
        required=False,
        widget=forms.Select(attrs={'autocomplete': 'off', 'id': 'id_team'})
    )

    # BusinessTeam & Admin metadata
    joining_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'autocomplete': 'off', 'id': 'id_joining_date'})
    )
    job_title = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'id': 'id_job_title'})
    )

    # ✅ Sales profile fields
    can_edit = forms.BooleanField(
        required=False,
        initial=False,
        label="Can Edit (Sales only)",
        widget=forms.CheckboxInput(attrs={'id': 'id_can_edit'})
    )
    can_change_years = forms.BooleanField(
        required=False,
        initial=False,
        label="Can Change Years (Sales only)",
        widget=forms.CheckboxInput(attrs={'id': 'id_can_change_years'})
    )

    # ✅ SalesHead profile field
    one_dp_only = forms.BooleanField(
        required=False,
        initial=False,
        label="One DP Only (Sales Head only)",
        widget=forms.CheckboxInput(attrs={'id': 'id_one_dp_only'})
    )

    # ✅ SalesOperation profile field (JSON list)
    editable_unit_fields = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'autocomplete': 'off',
            'id': 'id_editable_unit_fields',
            'rows': 3,
            'placeholder': 'e.g. price,status OR ["price","status"]'
        }),
        help_text='Provide JSON array or comma-separated values.'
    )

    # ✅ Viewer profile field (JSON list)
    allowed_pages = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'autocomplete': 'off',
            'id': 'id_allowed_pages',
            'rows': 3,
            'placeholder': 'e.g. dashboard,map OR ["dashboard","map"]'
        }),
        help_text='Provide JSON array or comma-separated values.'
    )

    class Meta:
        model = User
        fields = ['email', 'full_name', 'role']
        widgets = {
            'email': forms.EmailInput(attrs={'autocomplete': 'off', 'id': 'id_email'}),
            'full_name': forms.TextInput(attrs={'autocomplete': 'off', 'id': 'id_full_name'}),
        }

    # -------------------------
    # Helpers
    # -------------------------
    @staticmethod
    def _parse_list(text: str):
        """
        Accepts:
          - JSON list string: ["a","b"]
          - comma-separated: a,b
          - empty => []
        Returns python list[str]
        """
        if not text:
            return []
        text = text.strip()
        if not text:
            return []
        # try JSON
        if text.startswith("[") and text.endswith("]"):
            import json
            try:
                val = json.loads(text)
                if isinstance(val, list):
                    return [str(x).strip() for x in val if str(x).strip()]
            except Exception:
                pass
        # fallback CSV
        parts = [p.strip() for p in text.split(",")]
        return [p for p in parts if p]

    def clean(self):
        cleaned_data = super().clean()

        # passwords
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        role = cleaned_data.get('role')
        company = cleaned_data.get('company')
        team = cleaned_data.get('team')

        # roles that require company
        company_required_roles = [
            'CompanyAdmin', 'Manager', 'SalesHead', 'Sales', 'SalesOperation', 'Uploader', 'Viewer'
        ]
        if role in company_required_roles and not company:
            raise forms.ValidationError("Company is required for this role.")

        # team rules
        if role not in ['Sales', 'SalesHead'] and team:
            raise forms.ValidationError("Team can only be assigned for Sales or Sales Head.")
        if role in ['Sales', 'SalesHead'] and team and company and team.company_id != company.id:
            raise forms.ValidationError("Selected team does not belong to the selected company.")

        # BusinessTeam requirements
        if role == 'BusinessTeam':
            if not cleaned_data.get('joining_date'):
                raise forms.ValidationError("Joining Date is required for Business Team.")
            if not cleaned_data.get('job_title'):
                raise forms.ValidationError("Job Title is required for Business Team.")

        # Admin joining date (optional but if you want to enforce, uncomment)
        # if role == 'Admin' and not cleaned_data.get('joining_date'):
        #     raise forms.ValidationError("Joining Date is required for Admin.")

        # Role-specific validation for JSON-ish inputs
        if role == 'SalesOperation':
            # validate parseable
            _ = self._parse_list(cleaned_data.get('editable_unit_fields') or "")
        if role == 'Viewer':
            _ = self._parse_list(cleaned_data.get('allowed_pages') or "")

        return cleaned_data



class ProjectMasterplanForm(forms.ModelForm):
    class Meta:
        model = ProjectMasterplan
        fields = ['image']
        
        

# Inherit from SetPasswordForm instead of PasswordChangeForm
class CustomPasswordChangeForm(SetPasswordForm): 
    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')

        # 1. Check Length
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")

        # 2. Check for Digit
        if not re.search(r'\d', password):
            raise ValidationError("Password must contain at least one number.")

        # 3. Check for Special Character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain at least one special character (e.g., @, #, $, %).")

        return password
    
    
    