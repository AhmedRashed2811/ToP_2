# ToP/utils/market_research_units_management_utils.py

from __future__ import annotations

import re
from datetime import datetime, date
from typing import Any, Dict, Optional, Tuple, List

from django.utils.dateparse import parse_date
from dateutil.parser import parse as dateutil_parse

# -------------------------------------------------------
# Shared helpers used by the service (NOT in views)
# -------------------------------------------------------

MONTH_ABBR = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def get_user_full_name(user) -> str:
    if not user:
        return ""
    return (
        getattr(user, "full_name", "") or
        f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or
        getattr(user, "username", "")
    )


# ---------------------------------------------- Parse dates in various formats including MM/DD/YYYY (8/1/2024)
def parse_flexible_date(date_str: Any, field_name: str):
    """Parse dates in various formats including MM/DD/YYYY (8/1/2024)"""
    if not date_str or not isinstance(date_str, str):
        return None, f"{field_name}: Empty or invalid date value"

    date_str = date_str.strip()

    # Try Django's built-in parser first
    date_obj = parse_date(date_str)
    if date_obj:
        return date_obj, None

    # Handle MM/DD/YYYY format (like 8/1/2024)
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", date_str):
        try:
            month, day, year = map(int, date_str.split("/"))
            return datetime(year, month, day).date(), None
        except ValueError:
            return None, f"{field_name}: Invalid date components in '{date_str}' (MM/DD/YYYY format expected)"

    # Try dateutil's flexible parser
    try:
        return dateutil_parse(date_str).date(), None
    except (ValueError, OverflowError):
        return None, f"{field_name}: Could not parse date from '{date_str}'. Valid formats: YYYY-MM-DD, MM/DD/YYYY"


def parse_update_endpoint_date(value: Any) -> Tuple[Optional[date], Optional[str]]:
    """
    Matches your update endpoint behavior:
    - if value like "Aug/24" (month/day but first char not digit) => current year
    - else tries %m/%d/%Y, %m-%d-%Y, %Y-%m-%d
    returns (date_obj, error_message)
    """
    if value is None or value == "":
        return None, None

    s = str(value).strip()

    # "Aug/24" pattern (month/day)
    if "/" in s and s and not s[0].isdigit():
        try:
            month, day = s.split("/")
            month_num = MONTH_ABBR.get(month)
            if not month_num:
                return None, f"date_of_update: Invalid month abbreviation '{month}'"
            return date(datetime.now().year, month_num, int(day)), None
        except Exception as e:
            return None, f"date_of_update: Invalid abbreviated date '{s}' ({str(e)})"

    # standard formats
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date(), None
        except ValueError:
            continue

    return None, f"date_of_update: Could not parse date '{s}'"


# ---------------------------------------------- Convert string to float, handling various number formats
def clean_numeric_value(value: Any, field_name: str):
    """Convert string to float, handling various number formats"""
    if value is None:
        return None, None

    if isinstance(value, (int, float)):
        return float(value), None

    try:
        cleaned = str(value).strip()
        cleaned = re.sub(r"[^\d.-]", "", cleaned)
        if not cleaned:
            return None, None
        return float(cleaned), None
    except (ValueError, TypeError):
        return None, f"{field_name}: Could not convert '{value}' to number"


def normalize_csv_row(row: Dict[str, Any], column_mapping: Dict[str, str]) -> Dict[str, Any]:
    """
    Matches your import normalization:
    - map headers via COLUMN_MAPPING
    - strip values
    - empty string -> None
    - replace NBSP
    """
    normalized: Dict[str, Any] = {}
    for k, v in row.items():
        if k is None:
            continue
        key = column_mapping.get(k.strip(), k.strip())

        if isinstance(v, str):
            v = v.strip().replace("\xa0", " ")
            if v == "":
                v = None

        normalized[key] = v
    return normalized


# ---------------------------------------------- Calculate Derived Fields
def calculate_derived_fields(unit):
    """
    Same logic you provided, unchanged (just moved out of views).
    NOTE: This function expects MarketUnitData to be importable from caller module.
    """
    from ..models import MarketUnitData  # local import to avoid circular import

    derived = {}

    # PSM
    if unit.unit_price and unit.bua and unit.bua != 0:
        derived["psm"] = round(unit.unit_price / unit.bua, 2)

    # Months from update
    if unit.date_of_update:
        days = (date.today() - unit.date_of_update).days
        months = min(12, round(days / 365.25 * 12))
        derived["months_from_update"] = f"{months:02d}"

    # Payment Yrs (Excel-style)
    if unit.project_name and unit.unit_type:
        related = MarketUnitData.objects.filter(
            project_name=unit.project_name,
            unit_type=unit.unit_type
        ).exclude(payment_yrs_raw__isnull=True).exclude(payment_yrs_raw="")

        raw_values = []
        for r in related:
            try:
                if str(r.payment_yrs_raw).replace(".", "", 1).isdigit():
                    raw_values.append(float(r.payment_yrs_raw))
                else:
                    numbers = re.findall(r"[\d.]+", str(r.payment_yrs_raw))
                    if numbers:
                        raw_values.append(float(numbers[0]))
            except Exception:
                continue

        if raw_values:
            min_val = min(raw_values)
            max_val = max(raw_values)

            if min_val == 0:
                payment_yrs = "Cash"
            elif min_val == max_val:
                payment_yrs = f"{int(min_val)} Yrs" if float(min_val).is_integer() else f"{min_val} Yrs"
            else:
                payment_yrs = f"{int(min_val)} Yrs - {int(max_val)} Yrs"
            derived["payment_yrs"] = payment_yrs

    # DP Percentage (Excel-style)
    if unit.project_name and unit.unit_type:
        related_dp = MarketUnitData.objects.filter(
            project_name=unit.project_name,
            unit_type=unit.unit_type
        ).exclude(down_payment__isnull=True)

        dp_values = []
        for r in related_dp:
            try:
                if r.down_payment and str(r.down_payment).strip():
                    dp_values.append(float(r.down_payment))
            except (ValueError, TypeError):
                continue

        if dp_values:
            min_dp = min(dp_values)
            max_dp = max(dp_values)

            if min_dp == max_dp:
                dp_percentage = f"{int(min_dp * 100)}%"
            else:
                dp_percentage = f"{int(min_dp * 100)}% - {int(max_dp * 100)}%"
            derived["dp_percentage"] = dp_percentage
        else:
            derived["dp_percentage"] = ""

    return derived
