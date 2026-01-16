from datetime import timedelta, datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional

def get_from_row(row, keys):
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def to_str(value):
    return str(value).strip() if value not in (None, "") else ""


def to_decimal(value):
    try:
        return Decimal(str(value)) if value not in (None, "") else None
    except InvalidOperation:
        return None

# ---------------------------------------------- Convert Excel serial (e.g., 45555) to a Python date.
def _excel_serial_to_date(v) -> Optional[date]:
    """
    Convert Excel serial (e.g., 45555) to a Python date.
    Excel's day 1 is 1899-12-31, but due to the 1900 leap-year bug the
    correct base to get real dates is 1899-12-30.
    """
    try:
        iv = int(float(v))
    except Exception:
        return None
    base = date(1899, 12, 30)
    return base + timedelta(days=iv)



def to_date(v) -> Optional[date]:
    """
    Accept common sheet forms:
      - Python date/datetime
      - Excel serial numbers (int/float)
      - Strings like YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY, with '-' or '/'
    Returns a date or None if empty/invalid.
    """
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()

    s = str(v).strip()
    if s in ("", "-", "—"):
        return None

    # Excel serial number?
    if isinstance(v, (int, float)) or s.replace(".", "", 1).isdigit():
        d = _excel_serial_to_date(v)
        if d:
            return d

    # Try common patterns
    fmts = [
        "%Y-%m-%d", "%Y/%m/%d",
        "%m/%d/%Y", "%m-%d-%Y",
        "%d/%m/%Y", "%d-%m-%Y",
        "%m/%d/%y", "%d/%m/%y",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    # Couldn’t parse — just return None so we don’t break the import
    return None
 