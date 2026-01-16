import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from django.core.exceptions import ObjectDoesNotExist

from ..models import GoogleServiceAccount


logger = logging.getLogger(__name__)


def gspread_client(company):
    """
    Returns an authorized gspread client for a company
    using its active GoogleServiceAccount.
    """
    try:
        service_account = GoogleServiceAccount.objects.get(
            company=company,
            is_active=True
        )
    except ObjectDoesNotExist:
        raise Exception(
            f"No active Google Service Account configured for company '{company.name}'"
        )

    credentials_info = service_account.get_service_account_data()

    # Fix multiline private key if stored with escaped newlines
    if credentials_info.get("private_key"):
        credentials_info["private_key"] = credentials_info["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )

    return gspread.authorize(creds)


def resolve_worksheet(sheet, gid=None, title=None):
    """
    Prefer selecting worksheet by gid (if provided), otherwise by title,
    else fall back to first worksheet.
    """
    if gid:
        try:
            return sheet.get_worksheet_by_id(int(gid))
        except Exception:
            pass

    if title:
        try:
            return sheet.worksheet(title)
        except Exception:
            pass

    return sheet.get_worksheet(0)


# ---------------------------------------------- Update all sales data in Google Sheet for the approved sales request
def update_google_sheet_sales_data(company, sales_request, cached_data):
    """
    Update all sales data in Google Sheet for the approved sales request.
    (Logic preserved from your helper, but now uses gspread_client + resolve_worksheet in this module.)
    """
    if not company.google_sheet_url:
        logger.warning(f"Company {company.name} has no Google Sheet URL configured")
        return

    # Get the unit code to search for
    unit_code = sales_request.unit.unit_code if sales_request.unit else ""

    if not unit_code:
        logger.warning("No unit code found in sales request")
        return

    try:
        # Get Google Sheets client
        gc = gspread_client(company)

        # Open the company's spreadsheet
        sh = gc.open_by_url(company.google_sheet_url)
        ws = resolve_worksheet(sh, company.google_sheet_gid, company.google_sheet_title)

        # Get all data and headers
        all_data = ws.get_all_records()
        headers = ws.row_values(1)  # header row

        # Find the target unit row
        found_row = None
        for row_idx, row_data in enumerate(all_data, start=2):  # start=2 because header row
            sheet_unit_code = (
                row_data.get("Unit Code")
                or row_data.get("Unit Code ")
                or row_data.get("UnitCode")
                or row_data.get("unit_code")
                or row_data.get("Code")
            )
            if sheet_unit_code == unit_code:
                found_row = row_idx
                break

        if not found_row:
            logger.warning(f"Unit '{unit_code}' not found in company '{company.name}' Google Sheet")
            return

        today = datetime.now()
        reservation_date = f"{today.month}/{today.day}/{today.year}"

        contract_payment_plan = None

        # Keep the same logic you had (index [0] is expected to exist)
        logger.debug(f"cached_data.get('payments', '')[0] = {cached_data.get('payments', '')[0]}")
        if cached_data.get("payments", "")[0] == 100:
            contract_payment_plan = "Cash"
        else:
            contract_payment_plan = f"{cached_data.get('tenor_years', '')} Yrs"

        updates = {
            "Status": "Reserved",
            "Salesman Name": sales_request.sales_man.full_name if sales_request.sales_man else "Unknown",
            "Salesman Email": sales_request.sales_man.email if sales_request.sales_man else "",
            "Client Id": sales_request.client_id,
            "Client Phone Number": sales_request.client_phone_number or "",
            "Sales Value": cached_data.get("final_price", ""),
            "Currency": cached_data.get("selected_currency_name", ""),
            "Adj Contract Payment Plan": contract_payment_plan,
            "Reservation Date": reservation_date
        }

        # Find column indices and update each field
        for column_name, new_value in updates.items():
            col_index = None

            for idx, header in enumerate(headers):
                if header.strip() == column_name:
                    col_index = idx + 1  # gspread is 1-based
                    break

            if col_index:
                ws.update_cell(found_row, col_index, new_value)
                logger.debug(f"Updated {column_name} to '{new_value}' for unit {unit_code}")
            else:
                logger.warning(f"Column '{column_name}' not found in sheet headers")

        logger.info(f"✅ Successfully updated Google Sheet for company '{company.name}' - Unit '{unit_code}'")

    except Exception as e:
        logger.error(f"Failed to update Google Sheet for company {company.name}: {str(e)}")
        raise
