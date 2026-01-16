import requests
from ..models import Unit

# ==========================================
# STRATEGY PATTERN IMPLEMENTATION
# ==========================================

class InventoryStrategy:
    def __init__(self, company):
        self.company = company

    def get_all_units(self, active_only=False, exclude_blocked=False):
        raise NotImplementedError

    def get_unit(self, unit_code):
        raise NotImplementedError

    def get_leads(self, user_email):
        """
        Base implementation checks if the company has a Leads API URL.
        If yes, it fetches live leads. If no, it returns empty.
        This allows 'Native' inventory to still connect to 'Live' CRM/ERP for clients.
        """
        if not self.company.erp_url_leads:
            return {}

        try:
            # Construct URL (Assuming endpoint expects email as path param or query)
            # Adjust format based on your specific ERP requirement:
            url = f"{self.company.erp_url_leads}{user_email}"
            
            headers = {}
            if self.company.erp_url_leads_key:
                headers["Authorization"] = f"Bearer {self.company.erp_url_leads_key}"
                headers["x-api-key"] = self.company.erp_url_leads_key

            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            
        except Exception as e:
            # Log error silently or print to console
            print(f"Leads Fetch Error for {self.company.name}: {e}")
            
        return {}


# --- Strategy: Native (Database Only for Units, Hybrid for Leads) ---
class NativeInventoryStrategy(InventoryStrategy):
    def get_all_units(self, active_only=False, exclude_blocked=False):
        qs = Unit.objects.filter(company=self.company)
        
        if active_only:
            # Logic for sales/clients: Hide locked/unavailable units
            # Also exclude units explicitly marked as locked by system
            return qs.filter(
                status="Available"
            )
        
        if exclude_blocked:
            # Logic for Finance Manager: Show all EXCEPT blocked
            qs = qs.exclude(status__in=["Blocked Development", "Blocked Sales", "Blocked Developement"])
            
        return qs

    def get_unit(self, unit_code):
        # Case-insensitive lookup for better UX
        return Unit.objects.filter(unit_code__iexact=unit_code, company=self.company).first()

    # Note: get_leads is inherited from the base InventoryStrategy class above,
    # so it will automatically work if erp_url_leads is configured.


# --- Factory ---
def get_inventory_strategy(company):
    """
    Always returns NativeInventoryStrategy for UNITS (Warehouse architecture).
    However, the strategy instance still has the ability to fetch LEADS live via the base class.
    """
    return NativeInventoryStrategy(company)