from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_delete
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.timezone import now  # Import the 'now' function for default dates
import secrets
import os
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)

        # Set a default joining_date if not provided
        if not extra_fields.get('joining_date'):
            from datetime import date
            extra_fields['joining_date'] = date.today()

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        return self.create_user(email, password, **extra_fields)


# ---------------- Custom User Model ----------------
class User(AbstractUser):
    username = None  # Remove username field
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    password = models.TextField()
    
    ROLE_CHOICES = [ 
        ('Admin', 'Admin'),
        ('CompanyUser', 'Company User'),
        ('Developer', 'Developer'),
        ('Manager', 'Company Manager'),
        ('BusinessTeam', 'Business Team'),
        ('CompanyController', 'Company Controller'),
        ('CompanyFinanceManager', 'Company Finance Manager'), 

    ]
    role = models.CharField(max_length=100, choices=ROLE_CHOICES, default='Company_User')
    joining_date = models.DateField(null=True, blank=True)  # Allow NULL values
    is_active = models.BooleanField(default=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'role']

    def __str__(self):
        return self.email




# models.py
from django.db import models
from django.utils.timezone import now

class CompanyType(models.TextChoices):
    NATIVE = "native", "Native"
    ERP = "erp", "ERP"
    GOOGLE_SHEETS = "google_sheets", "Google Sheets"

class Company(models.Model):
    name = models.CharField(max_length=255, unique=True)
    num_users = models.IntegerField(default=0)
    subscription_start_date = models.DateField(default=now)
    subscription_end_date = models.DateField(default=now)
    joining_date = models.DateField(default=now)
    is_active = models.BooleanField(default=True)

    # 🔄 NEW unified type instead of is_native:
    company_type = models.CharField(
        max_length=20,
        choices=CompanyType.choices,
        default=CompanyType.NATIVE,
    )
    
    comp_type = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of active modules: ['native', 'erp', 'google_sheets']"
    )
    
    @property
    def has_erp(self):
        """Returns True if ERP URL is present."""
        return bool(self.erp_url)

    @property
    def has_google_sheets(self):
        """Returns True if Google Sheet URL is present."""
        return bool(self.google_sheet_url)

    def __str__(self):
        return self.name

    # ===== ERP fields (only for company_type='erp') =====
    erp_url = models.CharField(max_length=120, blank=True, null=True)
    erp_url_units = models.CharField(max_length=120, blank=True, null=True)
    erp_url_unit = models.CharField(max_length=120, blank=True, null=True)
    erp_url_leads = models.CharField(max_length=120, blank=True, null=True)
    erp_url_key = models.CharField(max_length=120, blank=True, null=True)
    erp_url_units_key = models.CharField(max_length=120, blank=True, null=True)
    erp_url_unit_key = models.CharField(max_length=120, blank=True, null=True)
    erp_url_leads_key = models.CharField(max_length=120, blank=True, null=True)

    # ===== Google Sheets fields (only for company_type='google_sheets') =====
    google_sheet_url = models.URLField(blank=True, null=True)
    google_sheet_gid = models.CharField(max_length=32, blank=True, null=True)      # keep as str to avoid casting issues
    google_sheet_title = models.CharField(max_length=128, blank=True, null=True)

    logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)

    def __str__(self):
        return self.name


# ---------------- Project Model ----------------
class Project(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    
    
    # Add this method:
    def __str__(self):
        return self.name


# ---------------- Company_User (One-to-One with User) ----------------
class CompanyUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    can_edit = models.BooleanField(default=False)
    can_change_years= models.BooleanField(default=False)


# ---------------- Company_User (One-to-One with User) ----------------
class CompanyManager(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)



class CompanyFinanceManager(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.email} - {self.company.name}"
    
    
# ---------------- Company_Controller (One-to-One with User) ----------------
class CompanyController(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    only_sales_operation = models.BooleanField(default=False) 


# ---------------- Project Web Configuration ----------------
class ProjectWebConfiguration(models.Model):
    PAYMENT_SCHEME_CHOICES = [
        ('Flat', 'Flat'),
        ('Flat Back Loaded', 'Flat Back Loaded'),
        ('Bullet', 'Bullet'),
        ('Bullet Back Loaded', 'Bullet Back Loaded'),
    ]
    
    project = models.OneToOneField(Project, on_delete=models.CASCADE)
    show_maintenance = models.BooleanField(default=False)
    show_standerd_price = models.BooleanField(default=False)
    show_gas = models.BooleanField(default=False)
    show_discount = models.BooleanField(default=False)
    show_payment_frequency = models.BooleanField(default=False)
    show_currecny = models.BooleanField(default=False)
    show_lead_name = models.BooleanField(default=False)
    show_lead_phone_number = models.BooleanField(default=False)
    show_payment_scheme = models.BooleanField(default=False)
    has_multiple_dp = models.BooleanField(default=False)
    default_timer_in_minutes = models.IntegerField(null=True, blank=True)
    period_between_DPs = models.IntegerField(null=True, blank=True)
    period_between_DP_and_intsallment = models.IntegerField(null=True, blank=True)
    
    show_additional_discount = models.BooleanField(default=False)
    additional_discount = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)  # percentage
    dp_for_additional_discount = models.IntegerField(null=True, blank=True)
    real_discount = models.BooleanField(default=False)
    
    show_not_availables_units_for_sales = models.BooleanField(
        default=False, 
        help_text="If True: Sales see ALL units. If False: Sales see ONLY Available units."
    )
    
    # --- NEW FIELD ---
    discount_after_discount = models.BooleanField(
        default=True, 
        help_text="If True: Apply discount on the discounted price. If False: Apply on original price."
    )
    
    # New field for payment schemes
    payment_schemes_to_show = models.JSONField(
        default=list,
        blank=True,
        help_text="List of payment schemes to show (Flat, Flat Back Loaded, Bullet, Bullet Back Loaded)"
    )
    
    allowed_years_for_sales = models.JSONField(
        default=list,
        blank=True,
        help_text="Optional list of allowed years for sales (1..12). Example: [1, 3, 5]"
    )
    
    one_dp_for_sales = models.BooleanField(
        default=False,
        help_text="If True: Sales flow uses one DP only (your business logic decides how to enforce)."
    )



class ProjectExtendedPayments(models.Model):
    project = models.ForeignKey('Project', on_delete=models.CASCADE)
    year = models.PositiveIntegerField(default=1)  # NEW
    scheme = models.CharField(max_length=255, default = "flat") 

    dp1 = models.FloatField(null=True, blank=True)
    dp2 = models.FloatField(null=True, blank=True)
    cumulative_dp1 = models.FloatField(null=True, blank=True)
    cumulative_dp2 = models.FloatField(null=True, blank=True)

    disable_additional_discount = models.BooleanField(default=False)

    for i in range(1, 49):
        locals()[f'installment_{i}'] = models.FloatField(null=True, blank=True)
        locals()[f'cumulative_{i}'] = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('project', 'year', 'scheme')

    def __str__(self):
        return f"Extended Payments for {self.project.name} - Year {self.year} - Scheme {self.scheme}"



class ProjectStanderdPayments(models.Model):
    project = models.OneToOneField('Project', on_delete=models.CASCADE)

    dp1 = models.FloatField(null=True, blank=True)
    dp2 = models.FloatField(null=True, blank=True)

    cumulative_dp1 = models.FloatField(null=True, blank=True)
    cumulative_dp2 = models.FloatField(null=True, blank=True)

    for i in range(1, 49):
        locals()[f'installment_{i}'] = models.FloatField(null=True, blank=True)
        locals()[f'cumulative_{i}'] = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Standerd Payments for {self.project.name}"




class ProjectExtendedPaymentsSpecialOffer(models.Model):
    project = models.ForeignKey('Project', on_delete=models.CASCADE)
    year = models.PositiveIntegerField(default=1)
    dp1 = models.FloatField(null=True, blank=True)
    dp2 = models.FloatField(null=True, blank=True)
    cumulative_dp1 = models.FloatField(null=True, blank=True)
    cumulative_dp2 = models.FloatField(null=True, blank=True)
    delivery_index = models.CharField(max_length=20, null=True, blank=True)
    constant_discount = models.FloatField(null=True, blank=True)

    for i in range(1, 49):
        locals()[f'installment_{i}'] = models.FloatField(null=True, blank=True)
        locals()[f'cumulative_{i}'] = models.FloatField(null=True, blank=True)
        
    def __str__(self):
        return f"Special Offer {self.year} years for {self.project.name} "

    class Meta:
        unique_together = ('project', 'year')





# ---------------- Project Configuration ----------------
class ProjectConfiguration(models.Model):

    project = models.OneToOneField(Project, on_delete=models.CASCADE)
    interest_rate = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    default_scheme = models.CharField(max_length=100, default='Flat')
    base_dp = models.DecimalField(max_digits=10, decimal_places=5,null=True, blank=True)
    base_tenor_years = models.IntegerField(null=True, blank=True)
    max_tenor_years = models.IntegerField(null=True, blank=True)
    days_until_unblocking = models.IntegerField(null=True, blank=True)
    variable_delivery_date = models.IntegerField(null=True, blank=True)
    base_payment_frequency = models.CharField(max_length=100)
    use_static_base_npv = models.BooleanField(default=False)
    # 👇 NEW FIELD
    maximum_requests_per_sales = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of customer requests assigned per sales rep (e.g., per day)."
    )

    def __str__(self):
        return f"Configuration for {self.project}"


# ---------------- Base NPV ----------------
class BaseNPV(models.Model):
    project_config = models.ForeignKey(ProjectConfiguration, on_delete=models.CASCADE)
    term_period = models.DecimalField(max_digits=10, decimal_places=2)
    npv_value = models.DecimalField(max_digits=18, decimal_places=5)

# ---------------- Gas Policy ----------------
class GasPolicy(models.Model):
    project_config = models.OneToOneField(ProjectConfiguration, on_delete=models.CASCADE)
    is_applied = models.BooleanField(default=False)
    gas_num_pmts = models.IntegerField(null=True, blank=True)
    scheduling = models.CharField(max_length=100, null=True, blank=True)

# ---------------- Gas Policy Fees ----------------
class GasPolicyFees(models.Model):
    gas_policy = models.ForeignKey(GasPolicy, on_delete=models.CASCADE)
    term_period = models.DecimalField(max_digits=10, decimal_places=2)
    fee_amount = models.DecimalField(max_digits=18, decimal_places=5)

# ---------------- Gas Policy Offsets ----------------
class GasPolicyOffsets(models.Model):
    gas_policy = models.ForeignKey(GasPolicy, on_delete=models.CASCADE)
    term_period = models.DecimalField(max_digits=10, decimal_places=2)
    offset_value = models.DecimalField(max_digits=10, decimal_places=2)
    



# ---------------- Constraints ----------------
class Constraints(models.Model):
    project_config = models.OneToOneField(ProjectConfiguration, on_delete=models.CASCADE)
    dp_min = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    dp_plus_first_pmt = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    dp_plus_first_plus_second_pmt = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    dp_plus_first_plus_second_plus_third_pmt = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    dp_plus_first_plus_second_plus_third_plus_forth_pmt = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    first_year_min = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    annual_min = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    max_discount = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    max_exception_discount = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)


# ---------------- Cash Till Delivery ----------------
class CTD(models.Model):
    project_constraints = models.ForeignKey('Constraints', on_delete=models.CASCADE, related_name="ctd_values")
    term_period = models.DecimalField(max_digits=10, decimal_places=2)
    npv_value = models.DecimalField(max_digits=18, decimal_places=5)

    def __str__(self):
        return f"CTD for {self.project_constraints} - Term: {self.term_period}, NPV: {self.npv_value}"


# ---------------- Maintenance Policy ----------------
class MaintenancePolicy(models.Model):
    project_config = models.OneToOneField(ProjectConfiguration, on_delete=models.CASCADE)
    is_applied = models.BooleanField(default=False)
    split_two_one_on_delivery = models.BooleanField(default=False)
    maintenance_num_pmts = models.IntegerField()


# ---------------- Maintenance Policy Offsets ----------------
class MaintenancePolicyOffsets(models.Model):
    maintenance_policy = models.ForeignKey(MaintenancePolicy, on_delete=models.CASCADE)
    term_period = models.DecimalField(max_digits=10, decimal_places=2)
    offset_value = models.DecimalField(max_digits=10, decimal_places=2)

# ---------------- Maintenance Policy Scheduling ----------------
class MaintenancePolicyScheduling(models.Model):
    maintenance_policy = models.ForeignKey(MaintenancePolicy, on_delete=models.CASCADE)
    term_period = models.DecimalField(max_digits=10, decimal_places=2)
    scheduling = models.CharField(max_length=100)

# ---------------- Business Analysis Team ----------------
class BusinessAnalysisTeam(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    joining_date = models.DateField()
    job_title = models.CharField(max_length=100)

class Unit(models.Model):
    # Primary Key
    unit_code = models.CharField(max_length=50, primary_key=True)
    
    # Basic Location Info
    city = models.CharField(max_length=255)
    project = models.CharField(max_length=255)  # Text name of project
    
    # Phasing & Type
    sales_phasing = models.CharField(max_length=255, null=True, blank=True)
    construction_phasing = models.CharField(max_length=255, null=True, blank=True)
    handover_phasing = models.CharField(max_length=255, null=True, blank=True)
    plot_type = models.CharField(max_length=255, null=True, blank=True)
    building_style = models.CharField(max_length=255, null=True, blank=True)
    building_type = models.CharField(max_length=255, null=True, blank=True)
    unit_type = models.CharField(max_length=255, null=True, blank=True)
    
    # Specs
    num_bedrooms = models.CharField(max_length=255, null=True, blank=True)
    num_bathrooms = models.IntegerField(null=True, blank=True)
    num_parking_slots = models.IntegerField(null=True, blank=True)
    
    # Areas
    footprint = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    net_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sellable_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Pricing (Base)
    base_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    cash_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    
    # Maintenance & Extras
    maintenance_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    maintenance_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    gas = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    parking_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    
    # Status & Dates
    status = models.CharField(max_length=255, null=True, blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    contract_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    
    # Final Pricing
    final_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)

    # Detailed Specs / Additional Fields
    unit_model = models.CharField(max_length=255, null=True, blank=True)
    mirror = models.CharField(max_length=255, null=True, blank=True)
    unit_position = models.CharField(max_length=255, null=True, blank=True)
    building_number = models.CharField(max_length=255, null=True, blank=True)
    floor = models.CharField(max_length=255, null=True, blank=True)
    sap_code = models.CharField(max_length=255, null=True, blank=True)
    finishing_specs = models.CharField(max_length=255, null=True, blank=True)
    
    # Detailed Areas
    internal_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    covered_terraces = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    uncovered_terraces = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    penthouse_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    garage_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    basement_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    common_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    roof_pergola_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    roof_terraces_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    bua = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    land_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    garden_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # PSM (Per Square Meter) Calculations
    net_area_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    covered_terraces_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    uncovered_terraces_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    penthouse_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    garage_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    basement_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    common_area_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    roof_pergola_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    roof_terraces_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    land_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    garden_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    base_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Views & Orientation
    main_view = models.CharField(max_length=255, null=True, blank=True)
    secondary_views = models.CharField(max_length=255, null=True, blank=True)
    levels = models.CharField(max_length=255, null=True, blank=True)
    north_breeze = models.CharField(max_length=255, null=True, blank=True)
    corners = models.CharField(max_length=255, null=True, blank=True)
    accessibility = models.CharField(max_length=255, null=True, blank=True)
    
    # Premiums & Discounts
    special_premiums = models.TextField(null=True, blank=True)
    special_discounts = models.TextField(null=True, blank=True)
    phasing = models.TextField(null=True, blank=True)
    
    total_premium_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_premium_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Payment Plans (Interest Free)
    interest_free_unit_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    interest_free_psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    interest_free_years = models.IntegerField(null=True, blank=True)
    
    # Payment Milestones
    down_payment_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    down_payment = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    contract_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    contract_payment = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    delivery_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    delivery_payment = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    
    # Blocking & Reservation
    club = models.CharField(max_length=255, null=True, blank=True)
    blocking_reason = models.CharField(max_length=255, null=True, blank=True)
    release_date = models.DateField(null=True, blank=True)
    blocking_date = models.DateField(null=True, blank=True)
    reservation_date = models.DateField(null=True, blank=True)
    
    # Contract Details
    contract_payment_plan = models.CharField(max_length=255, null=True, blank=True)
    contract_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    collected_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    collected_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    contract_delivery_date = models.DateField(null=True, blank=True)
    grace_period_months = models.IntegerField(null=True, blank=True)
    
    # Delivery Dates
    construction_delivery_date = models.DateField(null=True, blank=True)
    development_delivery_date = models.DateField(null=True, blank=True)
    client_handover_date = models.DateField(null=True, blank=True)
    
    # Stakeholders
    contractor_type = models.CharField(max_length=255, null=True, blank=True)
    contractor = models.CharField(max_length=255, null=True, blank=True)
    customer = models.CharField(max_length=255, null=True, blank=True)
    broker = models.CharField(max_length=255, null=True, blank=True)
    bulks = models.CharField(max_length=255, null=True, blank=True)
    
    # Sales Analytics
    direct_indirect_sales = models.CharField(max_length=255, null=True, blank=True)
    sales_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    psm = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area_range = models.CharField(max_length=255, null=True, blank=True)
    release_year = models.IntegerField(null=True, blank=True)
    sales_year = models.IntegerField(null=True, blank=True)
    adj_status = models.CharField(max_length=255, null=True, blank=True)
    ams = models.CharField(max_length=255, null=True, blank=True)

    # Relationships
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name="units")
    project_company = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name="units")

    # New Field: Source
    source = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.unit_code
    



class SalesRequest(models.Model):
    sales_man = models.ForeignKey('User', on_delete=models.CASCADE, related_name='sales_requests')  # Reference to your custom User model
    client_id = models.CharField(max_length=100)
    company = models.ForeignKey(Company, on_delete=models.CASCADE,null = True, blank = True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE,null = True, blank = True)
    unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, related_name='sales_requests',null = True, blank = True)
    date = models.DateTimeField(default=now)
    discount = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    final_price = models.DecimalField(max_digits=20, decimal_places=5, null=True, blank=True)
    client_name = models.CharField(max_length=255, null=True, blank=True)
    client_phone_number = models.CharField(max_length=255, null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    is_fake = models.BooleanField(default=False)
    payment_plan_data = models.JSONField(null=True, blank=True, help_text="Stores the snapshot of payments, installments, and calculations.")
    
    # --- NEW FIELD ---
    extended_minutes = models.IntegerField(default=0, null=True, blank=True)

    # --- NEW HELPER PROPERTY ---
    @property
    def expiration_date(self):
        """Calculates when the request expires based on Config + Extensions"""
        base_minutes = 0
        
        # specific logic to get minutes from ProjectWebConfiguration
        if self.project and hasattr(self.project, 'projectwebconfiguration'):
            config = self.project.projectwebconfiguration
            if config.default_timer_in_minutes:
                base_minutes = config.default_timer_in_minutes

        total_minutes = base_minutes + self.extended_minutes
        return self.date + timedelta(minutes=total_minutes)

    def __str__(self):
        unit_code = self.unit.unit_code if self.unit else "------"
        sales_man = self.sales_man.full_name if self.sales_man else "Unknown Salesman"
        return f"SalesRequest by {sales_man} for Unit {unit_code}"
    

class SalesRequestAnalytical(models.Model):
    sales_man = models.ForeignKey('User', on_delete=models.CASCADE, related_name='sales_requests_analytical')  # Reference to your custom User model
    client_id = models.CharField(max_length=100)
    company = models.ForeignKey(Company, on_delete=models.CASCADE,null = True, blank = True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE,null = True, blank = True)

    unit_code = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    base_price = models.FloatField(null=True, blank=True)
    
    date = models.DateTimeField(default=now)
    discount = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True)
    final_price = models.DecimalField(max_digits=20, decimal_places=5, null=True, blank=True)
    client_name = models.CharField(max_length=255, null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    is_fake = models.BooleanField(default=False)

    def __str__(self):
        unit_code = self.unit.unit_code if self.unit else "------"
        sales_man = self.sales_man.full_name if self.sales_man else "Unknown Salesman"
        return f"SalesRequest by {sales_man} for Unit {unit_code}"


class ModificationRecords(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=255)
    description = models.CharField(max_length = 300, null=True, blank=True)
    timestamp = models.DateTimeField(default=now)  # 👈 added datetime with default


class MarketProjectLocation(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class MarketProjectDeveloper(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class MarketUnitType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class MarketUnitAssetType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class MarketUnitFinishingSpec(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class MarketProject(models.Model):
    name = models.CharField(max_length=255)
    developer = models.ForeignKey(MarketProjectDeveloper, on_delete=models.CASCADE)
    location = models.ForeignKey(MarketProjectLocation, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    govern = models.CharField(max_length=255, null=True, blank=True) 

    def __str__(self):
        return self.name



class MarketUnitData(models.Model):
    project_name = models.CharField(max_length=255,null=True, blank=True)
    developer_name = models.CharField(max_length=255,null=True, blank=True)
    location = models.CharField(max_length=255,null=True, blank=True)
    asset_type = models.CharField(max_length=255,null=True, blank=True)
    unit_type = models.CharField(max_length=255,null=True, blank=True)

    bua = models.FloatField(null=True, blank=True)
    land_area = models.FloatField(null=True, blank=True)
    garden = models.FloatField(null=True, blank=True)
    unit_price = models.FloatField(null=True, blank=True)
    psm = models.FloatField(null=True, blank=True)

    payment_yrs_raw = models.TextField(null=True, blank=True)
    payment_yrs = models.CharField(max_length=255, null=True, blank=True)
    down_payment = models.FloatField(null=True, blank=True)
    delivery_percentage = models.FloatField(null=True, blank=True)
    cash_discount = models.FloatField(null=True, blank=True)

    delivery_date = models.CharField(max_length=255, null=True, blank=True)
    finishing_specs = models.CharField(max_length=255, null=True, blank=True)
    maintenance = models.FloatField(null=True, blank=True)
    phase = models.FloatField(null=True, blank=True)

    date_of_update = models.DateField(auto_now_add=False, null=True, blank=True)
    updated_by = models.TextField(null=True, blank=True)
    source_of_info = models.TextField(null=True, blank=True)
    months_from_update = models.IntegerField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    dp_percentage = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.project_name} - {self.unit_type}"
    



 

class PricingPremiumGroup(models.Model):
    name = models.CharField(max_length=255)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="pricing_groups")
    

    class Meta:
        unique_together = ('name', 'project') # Prevent duplicate group names within a project
        ordering = ['name']

    def __str__(self):
        return f"{self.project.name} - {self.name}"


class PricingPremiumSubgroup(models.Model):
    name = models.CharField(max_length=255)
    premium_group = models.ForeignKey(PricingPremiumGroup, on_delete=models.CASCADE, related_name="subgroups")
    value = models.FloatField(default= 0)


    class Meta:
        unique_together = ('name', 'premium_group') # Prevent duplicate subgroup names within a group
        ordering = [ 'name']

    def __str__(self):
        return f"{self.premium_group} - {self.name}"


class PricingCriteria(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="pricing_criterias")

    # --- Unit Identification ---
    unit_model = models.CharField(max_length=255)

    # --- BUA (Built-Up Area) ---
    bua_price_per_square_meter = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    extra_bua_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    extra_bua_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # Assuming percentage like 5.00 for 5%

    # --- Terrace ---
    terrace_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    terrace_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    terrace_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # Added missing field name 'terrace_area'

    # --- Penthouse ---
    penthouse_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    penthouse_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    extra_penthouse_price_per_square_meter = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    extra_penthouse_percentage_per_square_meter = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # --- Roof ---
    roof_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    roof_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    extra_roof_price_per_square_meter = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True) # Note: Typo preserved from your list
    extra_roof_percentage_per_square_meter = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # Note: Typo preserved from your list

    # --- Land ---
    land_price_per_square_meter = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    land_percentage_per_square_meter = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # Note: Name adjusted from your list
    extra_land_price_per_square_meter = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    extra_land_percentage_per_square_meter = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # Note: Name adjusted from your list

    # Optional: Add a timestamp for when the criteria was created/updated
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Ensure only one set of criteria per project/unit_model combination
        unique_together = ('project', 'unit_model')

    def __str__(self):
        return f"Criteria for {self.unit_model} - Project {self.project.name}"
    
    
    
    
class GoogleServiceAccount(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='google_service_account')
    project_id = models.CharField(max_length=255)
    private_key_id = models.CharField(max_length=255)
    private_key = models.TextField()  # Store the entire private key
    client_email = models.EmailField()
    client_id = models.CharField(max_length=255)
    auth_uri = models.URLField(default="https://accounts.google.com/o/oauth2/auth")
    token_uri = models.URLField(default="https://oauth2.googleapis.com/token")
    auth_provider_x509_cert_url = models.URLField(default="https://www.googleapis.com/oauth2/v1/certs")
    client_x509_cert_url = models.URLField()
    universe_domain = models.CharField(max_length=100, default="googleapis.com")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Google Service Account - {self.company.name}"

    def get_service_account_data(self):
        """Return the service account data in the format needed for gspread"""
        return {
            "type": "service_account",
            "project_id": self.project_id,
            "private_key_id": self.private_key_id,
            "private_key": self.private_key,
            "client_email": self.client_email,
            "client_id": self.client_id,
            "auth_uri": self.auth_uri,
            "token_uri": self.token_uri,
            "auth_provider_x509_cert_url": self.auth_provider_x509_cert_url,
            "client_x509_cert_url": self.client_x509_cert_url,
            "universe_domain": self.universe_domain
        }
        
        
class ProjectMasterplan(models.Model):
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='masterplan')
    image = models.ImageField(upload_to='masterplans/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Masterplan for {self.project.name}"

class UnitPosition(models.Model):
    UNIT_TYPE_CHOICES = [
        ('single', 'Single Unit'),
        ('building', 'Building'),
    ]
    
    masterplan = models.ForeignKey(ProjectMasterplan, on_delete=models.CASCADE, related_name='unit_positions')
    unit_code = models.CharField(max_length=50)
    x_percent = models.DecimalField(max_digits=6, decimal_places=3)  # X coordinate as percentage (0-100)
    y_percent = models.DecimalField(max_digits=6, decimal_places=3)  # Y coordinate as percentage (0-100)
    unit_type = models.CharField(max_length=10, choices=UNIT_TYPE_CHOICES, default='single')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['masterplan', 'unit_code']
    
    def __str__(self):
        return f"{self.unit_code} at ({self.x_percent}, {self.y_percent})"
    
    
# Add this new model below UnitPosition
class UnitPositionChild(models.Model):
    position = models.ForeignKey(UnitPosition, on_delete=models.CASCADE, related_name='child_units')
    unit_code = models.CharField(max_length=50)
    
    def __str__(self):
        return f"{self.unit_code} in {self.position}"




# --- New Model for Unit Layouts ---
class UnitLayout(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='layouts')
    building_type = models.CharField(max_length=255)
    unit_type = models.CharField(max_length=255)
    unit_model = models.CharField(max_length=255)
    image = models.ImageField(upload_to='unit_layouts/')
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    def __str__(self):
        return f"{self.project.name} - {self.unit_model}"



# ---------------- Attendance Logic ----------------
class AttendanceLog(models.Model):
    ACTION_CHOICES = (
        ('IN', 'Check In'),
        ('OUT', 'Check Out'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=3, choices=ACTION_CHOICES)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    photo = models.ImageField(upload_to='attendance_photos/%Y/%m/%d/')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.timestamp}"



# --- Signal to Auto-Delete File from Storage ---
@receiver(post_delete, sender=UnitLayout)
def delete_layout_file(sender, instance, **kwargs):
    """Deletes the file from filesystem when the database record is deleted."""
    if instance.image:
        if os.path.isfile(instance.image.path):
            try:
                os.remove(instance.image.path)
            except Exception as e:
                print(f"Error deleting file: {e}")