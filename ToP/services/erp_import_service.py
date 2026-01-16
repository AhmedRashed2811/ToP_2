import requests
import logging
from typing import List, Dict, Any
from ..models import Company
from ..utils.csv_inventory_utils import convert_date_format  # Import the fix

logger = logging.getLogger(__name__)

class ERPImportService:
    """
    Connects to external ERP systems to fetch Unit data.
    """

    @staticmethod
    def fetch_units(company: Company) -> List[Dict[str, Any]]:
        """
        Requests data from company.erp_url and maps it to Unit Warehouse format.
        """
        if not company.erp_url:
            raise ValueError("ERP URL is not configured for this company.")

        # 1. Prepare Headers (Auth)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ToP-Warehouse/1.0"
        }
        if company.erp_url_key:
            headers["Authorization"] = f"Bearer {company.erp_url_key}"
            headers["x-api-key"] = company.erp_url_key

        # 2. Make Request
        try:
            response = requests.get(company.erp_url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise ValueError(f"ERP Connection Failed: {str(e)}")

        # 3. Validate Response Structure
        results = []
        if isinstance(data, list):
            results = data
        elif isinstance(data, dict) and "results" in data:
            results = data["results"]
        elif isinstance(data, dict) and "data" in data:
            results = data["data"]
        else:
            if isinstance(data, dict) and (data.get("unit_code") or data.get("id")):
                results = [data]
            else:
                raise ValueError("ERP response format not recognized. Expected list or {'results': []}.")

        # 4. Map Fields
        standardized_units = []
        for item in results:
            unit_data = ERPImportService._map_erp_item(item)
            if unit_data.get('unit_code'):
                standardized_units.append(unit_data)

        return standardized_units

    @staticmethod
    def _map_erp_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps generic ERP keys to Django Unit Model keys.
        Checks for snake_case, camelCase, and Title Case variations.
        """
        def get_val(*keys):
            for k in keys:
                if k in item and item[k] is not None:
                    return item[k]
            return None
        
        # Helper to get date and convert immediately
        def get_date_val(*keys):
            raw = get_val(*keys)
            return convert_date_format(raw)

        # --- MAPPING START ---
        mapped = {}

        # Primary Key & Basics
        mapped['unit_code'] = get_val("unit_code", "unitCode", "Unit Code", "id", "Code", "code")
        mapped['city'] = get_val("city", "City", "location")
        mapped['project'] = get_val("project", "Project", "project_name", "projectName")

        # Phasing & Type
        mapped['sales_phasing'] = get_val("sales_phasing", "salesPhasing", "Sales Phasing", "phase")
        mapped['construction_phasing'] = get_val("construction_phasing", "constructionPhasing", "Construction Phasing")
        mapped['handover_phasing'] = get_val("handover_phasing", "handoverPhasing", "Handover Phasing")
        mapped['plot_type'] = get_val("plot_type", "plotType", "Plot Type")
        mapped['building_style'] = get_val("building_style", "buildingStyle", "Bld. Style")
        mapped['building_type'] = get_val("building_type", "buildingType", "Bld. Type")
        mapped['unit_type'] = get_val("unit_type", "unitType", "Unit Type", "type")

        # Specs
        mapped['num_bedrooms'] = get_val("num_bedrooms", "bedrooms", "No. of Bed Rooms", "Bedrooms")
        mapped['num_bathrooms'] = get_val("num_bathrooms", "bathrooms", "No. of Bathrooms", "Bathrooms")
        mapped['num_parking_slots'] = get_val("num_parking_slots", "parking_slots", "No. of Parking Slots")

        # Areas
        mapped['footprint'] = get_val("footprint", "Foot print")
        mapped['net_area'] = get_val("net_area", "netArea", "Unit Area (Net Area)")
        mapped['sellable_area'] = get_val("sellable_area", "sellableArea", "Gross Area", "Sellable Area")
        mapped['total_area'] = get_val("total_area", "totalArea", "Total Area")
        mapped['internal_area'] = get_val("internal_area", "internalArea", "Internal Area")
        mapped['covered_terraces'] = get_val("covered_terraces", "coveredTerraces", "Covered Terraces")
        mapped['uncovered_terraces'] = get_val("uncovered_terraces", "uncoveredTerraces", "Uncovered Terraces")
        mapped['penthouse_area'] = get_val("penthouse_area", "penthouseArea", "Penthouse Area")
        mapped['garage_area'] = get_val("garage_area", "garageArea", "Garage Area")
        mapped['basement_area'] = get_val("basement_area", "basementArea", "Basement Area")
        mapped['common_area'] = get_val("common_area", "commonArea", "Common Area")
        mapped['roof_pergola_area'] = get_val("roof_pergola_area", "roofPergolaArea", "Roof Pergola Area")
        mapped['roof_terraces_area'] = get_val("roof_terraces_area", "roofTerracesArea", "Roof Terraces Area")
        mapped['bua'] = get_val("bua", "BUA", "B.U.A.")
        mapped['land_area'] = get_val("land_area", "landArea", "Land Area")
        mapped['garden_area'] = get_val("garden_area", "gardenArea", "Garden Area")

        # Pricing (Base)
        mapped['base_price'] = get_val("base_price", "basePrice", "Unit Base Price", "price", "list_price")
        mapped['cash_price'] = get_val("cash_price", "cashPrice", "Cash Price")
        mapped['final_price'] = get_val("final_price", "finalPrice")
        mapped['discount'] = get_val("discount")

        # Maintenance & Extras
        mapped['maintenance_percent'] = get_val("maintenance_percent", "maintenancePercent", "Maintenance %")
        mapped['maintenance_value'] = get_val("maintenance_value", "maintenanceValue", "Maintenance Value")
        mapped['gas'] = get_val("gas", "Gas")
        mapped['parking_price'] = get_val("parking_price", "parkingPrice", "Parking Price")
        mapped['club'] = get_val("club", "Club")

        # Status
        mapped['status'] = get_val("status", "Status", "availability")
        mapped['blocking_reason'] = get_val("blocking_reason", "blockingReason", "Blocking Reason")

        # --- DATES (Converted) ---
        mapped['contract_date'] = get_date_val("contract_date", "contractDate", "Contract Date")
        mapped['delivery_date'] = get_date_val("delivery_date", "deliveryDate", "Delivery Date")
        mapped['release_date'] = get_date_val("release_date", "releaseDate", "Release Date")
        mapped['blocking_date'] = get_date_val("blocking_date", "blockingDate", "Blocking Date")
        mapped['reservation_date'] = get_date_val("reservation_date", "reservationDate", "Reservation Date")
        
        mapped['contract_delivery_date'] = get_date_val("contract_delivery_date", "contractDeliveryDate", "Contract Delivery Date")
        mapped['construction_delivery_date'] = get_date_val("construction_delivery_date", "constructionDeliveryDate", "Construction Delivery Date")
        mapped['development_delivery_date'] = get_date_val("development_delivery_date", "developmentDeliveryDate", "Development Delivery Date")
        mapped['client_handover_date'] = get_date_val("client_handover_date", "clientHandoverDate", "Client Handover Date")

        # Detailed Specs / Additional Fields
        mapped['unit_model'] = get_val("unit_model", "unitModel", "Unit Model")
        mapped['mirror'] = get_val("mirror", "Mirror")
        mapped['unit_position'] = get_val("unit_position", "unitPosition", "Unit Position")
        mapped['building_number'] = get_val("building_number", "buildingNumber", "Building Number", "building")
        mapped['floor'] = get_val("floor", "Floor")
        mapped['sap_code'] = get_val("sap_code", "sapCode", "SAP Code")
        mapped['finishing_specs'] = get_val("finishing_specs", "finishingSpecs", "Finishing Specs")

        # PSM
        mapped['net_area_psm'] = get_val("net_area_psm", "netAreaPSM", "Net Area PSM")
        mapped['base_psm'] = get_val("base_psm", "basePSM", "Base PSM")
        mapped['psm'] = get_val("psm", "PSM")

        # Views & Orientation
        mapped['main_view'] = get_val("main_view", "mainView", "Main View")
        mapped['secondary_views'] = get_val("secondary_views", "secondaryViews", "Secondary Views")
        mapped['levels'] = get_val("levels", "Levels")
        mapped['north_breeze'] = get_val("north_breeze", "northBreeze", "North Breeze")
        mapped['corners'] = get_val("corners", "Corners")
        mapped['accessibility'] = get_val("accessibility", "Accessibility")

        # Premiums
        mapped['special_premiums'] = get_val("special_premiums", "specialPremiums")
        mapped['special_discounts'] = get_val("special_discounts", "specialDiscounts")
        mapped['phasing'] = get_val("phasing")
        mapped['total_premium_percent'] = get_val("total_premium_percent", "totalPremiumPercent", "Total Premium %")
        mapped['total_premium_value'] = get_val("total_premium_value", "totalPremiumValue", "Total Premium Value")

        # Payment Plans / Analytics
        mapped['interest_free_unit_price'] = get_val("interest_free_unit_price", "interestFreeUnitPrice", "Interest Free Unit Price")
        mapped['interest_free_psm'] = get_val("interest_free_psm", "interestFreePSM", "Interest Free PSM")
        mapped['interest_free_years'] = get_val("interest_free_years", "interestFreeYears", "Interest Free Yrs.")
        mapped['down_payment_percent'] = get_val("down_payment_percent", "downPaymentPercent", "Down Payment %")
        mapped['down_payment'] = get_val("down_payment", "downPayment", "Down Payment")
        mapped['contract_percent'] = get_val("contract_percent", "contractPercent", "Contract %")
        mapped['contract_payment'] = get_val("contract_payment", "contractPayment", "Contract Payment")
        mapped['delivery_percent'] = get_val("delivery_percent", "deliveryPercent", "Delivery %")
        mapped['delivery_payment'] = get_val("delivery_payment", "deliveryPayment", "Delivery Payment")
        
        # Contract Details
        mapped['contract_payment_plan'] = get_val("contract_payment_plan", "contractPaymentPlan")
        mapped['contract_value'] = get_val("contract_value", "contractValue")
        mapped['collected_amount'] = get_val("collected_amount", "collectedAmount")
        mapped['collected_percent'] = get_val("collected_percent", "collectedPercent")
        mapped['grace_period_months'] = get_val("grace_period_months", "gracePeriodMonths")
        
        # Stakeholders & Analytics
        mapped['contractor_type'] = get_val("contractor_type", "contractorType")
        mapped['contractor'] = get_val("contractor")
        mapped['customer'] = get_val("customer")
        mapped['broker'] = get_val("broker")
        mapped['bulks'] = get_val("bulks")
        mapped['direct_indirect_sales'] = get_val("direct_indirect_sales", "directIndirectSales")
        mapped['sales_value'] = get_val("sales_value", "salesValue")
        mapped['area_range'] = get_val("area_range", "areaRange")
        mapped['release_year'] = get_val("release_year", "releaseYear")
        mapped['sales_year'] = get_val("sales_year", "salesYear")
        mapped['adj_status'] = get_val("adj_status", "adjStatus")
        mapped['ams'] = get_val("ams", "AMS")

        # Return dict without None values so partial updates work
        return {k: v for k, v in mapped.items() if v is not None}