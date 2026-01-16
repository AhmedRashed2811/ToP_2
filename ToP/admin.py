from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from .models import *


admin.site.register(User)
admin.site.register(Project)
admin.site.register(CompanyController)
admin.site.register(CompanyUser)
admin.site.register(CompanyManager)
admin.site.register(BusinessAnalysisTeam)
admin.site.register(Company)
admin.site.register(CTD)
admin.site.register(BaseNPV)
admin.site.register(ProjectConfiguration)
admin.site.register(ProjectExtendedPayments)
admin.site.register(ProjectExtendedPaymentsSpecialOffer)
admin.site.register(ProjectStanderdPayments)
admin.site.register(ProjectWebConfiguration)
admin.site.register(Constraints)
admin.site.register(GasPolicy)
admin.site.register(GasPolicyFees)
admin.site.register(GasPolicyOffsets)
admin.site.register(Unit)
admin.site.register(MaintenancePolicyScheduling)
admin.site.register(MaintenancePolicyOffsets)
admin.site.register(MaintenancePolicy)
admin.site.register(SalesRequest)
admin.site.register(SalesRequestAnalytical)
admin.site.register(ModificationRecords)
admin.site.register(GoogleServiceAccount)
# admin.site.register(ProjectDiscountRates) 

admin.site.register(MarketUnitType)
admin.site.register(MarketProject)
admin.site.register(MarketProjectDeveloper)
admin.site.register(MarketProjectLocation)
admin.site.register(MarketUnitFinishingSpec)
admin.site.register(MarketUnitAssetType)
admin.site.register(MarketUnitData)
admin.site.register(PricingPremiumGroup)
admin.site.register(PricingPremiumSubgroup)
admin.site.register(PricingCriteria)
admin.site.register(ProjectMasterplan)
admin.site.register(UnitPosition)
admin.site.register(UnitPositionChild)



