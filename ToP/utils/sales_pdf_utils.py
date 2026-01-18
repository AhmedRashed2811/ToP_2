# ToP/utils/sales_pdf_utils.py

from __future__ import annotations

from typing import Any, Dict, List

from django.utils.dateparse import parse_datetime
from django.utils.formats import date_format


def get_unit_details(sales_request):
    """Extract unit details from sales request (unchanged)."""
    if sales_request.unit:
        return {
            "bedrooms": getattr(sales_request.unit, "num_bedrooms", "N/A"),
            "area": getattr(sales_request.unit, "gross_area", "N/A"),
            "finishing": getattr(sales_request.unit, "finishing_specs", "N/A"),
            "garden_area": getattr(sales_request.unit, "garden_area", "N/A"),
            "delivery_date": getattr(sales_request.unit, "development_delivery_date", "N/A"),
        }
    return {
        "bedrooms": "N/A",
        "area": "N/A",
        "finishing": "N/A",
        "garden_area": "N/A",
        "delivery_date": "N/A",
    }


def resolve_actual_unit_code(sales_request) -> str:
    """
    Determine the actual unit code string for display/filename.
    (Preserves your original behavior.)
    """
    if sales_request.unit:
        return sales_request.unit.unit_code or ""
    return ""


def build_sales_pdf_rows(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build rows + totals (preserves original logic exactly).
    Returns:
      {
        rows, final_price, currency,
        has_maintenance, has_gas,
        total_maintenance_str, total_gas_str
      }
    """
    dates = data.get("dates", [])
    payments = data.get("payments", [])
    maintenance_fees = data.get("maintenance_fees", [])
    gas_fees = data.get("gas_fees", [])
    final_price = float(data.get("final_price", 0.0))
    currency = data.get("selected_currency_name", "EGP")

    has_maintenance = any(maintenance_fees)
    has_gas = any(gas_fees)

    rows: List[Dict[str, Any]] = []
    cumulative_percentage = 0
    total_maintenance = 0
    total_gas = 0

    for idx, date_str in enumerate(dates):
        # date formatting (same)
        try:
            date_obj = parse_datetime(date_str)
            formatted_date = date_format(date_obj, "Y-m-d") if date_obj else "-"
        except Exception:
            formatted_date = "-"

        # payment/amount (same)
        payment_percent = payments[idx] if idx < len(payments) else 0
        payment_str = f"{round(payment_percent, 2):.2f}%"
        amount = final_price * (payment_percent / 100)
        amount_str = f"{round(amount):,}"

        # cumulative (same)
        cumulative_percentage += payment_percent
        cumulative_str = f"{cumulative_percentage:.2f}%"

        # maintenance (same)
        if has_maintenance and idx < len(maintenance_fees) and maintenance_fees[idx]:
            try:
                maintenance_value = float(maintenance_fees[idx])
                total_maintenance += maintenance_value
                maintenance_str = f"{round(maintenance_value):,}"
            except (ValueError, TypeError):
                maintenance_str = "-"
        else:
            maintenance_str = "-"

        # gas (same)
        if has_gas and idx < len(gas_fees) and gas_fees[idx]:
            try:
                gas_value = float(gas_fees[idx])
                total_gas += gas_value
                gas_str = f"{round(gas_value):,}"
            except (ValueError, TypeError):
                gas_str = "-"
        else:
            gas_str = "-"

        rows.append(
            {
                "index": idx + 1,
                "date": formatted_date,
                "payment": payment_str,
                "amount": amount_str,
                "maintenance": maintenance_str,
                "gas": gas_str,
                "cumulative": cumulative_str,
            }
        )

    total_maintenance_str = f"{round(total_maintenance):,}" if has_maintenance else "0"
    total_gas_str = f"{round(total_gas):,}" if has_gas else "0"

    return {
        "rows": rows,
        "final_price": final_price,
        "currency": currency,
        "has_maintenance": has_maintenance,
        "has_gas": has_gas,
        "total_maintenance_str": total_maintenance_str,
        "total_gas_str": total_gas_str,
    }
