# ToP/utils/units_pdf_utils.py

import io
from collections import defaultdict
from datetime import datetime

from django.template.loader import get_template
from xhtml2pdf import pisa

# If you already have month_map elsewhere, keep it there and import it.
# Otherwise define it here.
month_map = {
    "JAN": "Jan", "FEB": "Feb", "MAR": "Mar", "APR": "Apr",
    "MAY": "May", "JUN": "Jun", "JUL": "Jul", "AUG": "Aug",
    "SEPT": "Sep", "SEP": "Sep", "OCT": "Oct", "NOV": "Nov", "DEC": "Dec"
}


def normalize_date_string(date_str: str) -> str:
    """
    Preserves your normalization logic for strings like:
    '01/SEPT/2026' -> '01/Sep/2026'
    """
    if not date_str:
        return date_str

    parts = str(date_str).upper().split("/")
    if len(parts) == 3:
        day, month, year = parts
        month = month_map.get(month[:4], month[:3].title())  # handle 'SEPT' or 'SEP'
        return f"{day}/{month}/{year}"
    return date_str


def summarize_by_date(units: list) -> list:
    """
    Preserves your logic:
    - aggregates amount/maintenance/gas by date across all units
    - totals amount_all to compute percent
    - sorts by date using two parsing patterns (try/except)
    - returns PMT labels and blank strings instead of zeros
    """
    summary = defaultdict(lambda: {"amount": 0, "maintenance": 0, "gas": 0})
    total_amount_all = 0

    for unit in units:
        for row in unit.get("payments", []):
            date = row.get("date")
            if date:
                try:
                    amount = float(
                        str(row.get("installment", "0"))
                        .replace("%", "")
                        .replace(",", "")
                        or 0
                    )
                    maintenance = float(str(row.get("maintenance", "0")).replace(",", "") or 0)
                    gas = float(str(row.get("gas", "0")).replace(",", "") or 0)

                    summary[date]["amount"] += amount
                    summary[date]["maintenance"] += maintenance
                    summary[date]["gas"] += gas

                    total_amount_all += amount
                except ValueError:
                    continue

    # Sort by date (preserved)
    try:
        sorted_summary = sorted(
            summary.items(),
            key=lambda x: datetime.strptime(normalize_date_string(x[0]), "%d/%b/%Y"),
        )
    except Exception:
        sorted_summary = sorted(
            summary.items(),
            key=lambda x: datetime.strptime(normalize_date_string(x[0]), "%b %d, %Y"),
        )

    # Format result with PMT labels and empty zeroes (preserved)
    result = []
    for idx, (date, values) in enumerate(sorted_summary, start=1):
        amount = values["amount"]
        maintenance = values["maintenance"]
        gas = values["gas"]
        percent = (amount / total_amount_all * 100) if total_amount_all else 0

        result.append(
            {
                "label": f"PMT {idx}",
                "date": date,
                "amount": amount if amount else "",
                "maintenance": maintenance if maintenance else "",
                "gas": gas if gas else "",
                "percent": round(percent, 2) if percent else "",
            }
        )

    return result


def render_units_pdf_bytes(*, units: list, template_path: str) -> tuple[bool, bytes | str]:
    """
    Renders the units PDF and returns:
      (True, pdf_bytes) on success
      (False, html_string) on error (preserves the ability to debug HTML)

    NOTE: This avoids returning HttpResponse from utils.
    """
    summary = summarize_by_date(units)
    template = get_template(template_path)
    html = template.render({"units": units, "summary": summary})

    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(
        io.BytesIO(html.encode("UTF-8")),
        dest=pdf_buffer,
        encoding="UTF-8",
    )

    if pisa_status.err:
        return False, html

    return True, pdf_buffer.getvalue()
