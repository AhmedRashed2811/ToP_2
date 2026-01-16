# ToP/utils/csv_inventory_utils.py

import csv
from io import StringIO
from typing import Dict, Any, List, Optional

import pandas as pd
from django.core.cache import cache
from django.http import JsonResponse
from django.core.files.storage import default_storage


from datetime import timedelta, datetime, date
import re
import pandas as pd

# ---------------------------------------------- Extract only digits from a value.
def clean_numeric(value):
    """ Extract only digits from a value (e.g., '2 B.' -> '2'). """
    if value:
        numbers = re.findall(r'\d+', str(value))  # Find numeric parts
        return int(numbers[0]) if numbers else None  # Convert first match to int
    return None


# ---------------------------------------------- Converts a date to 'YYYY-MM-DD' format.
def convert_date_format(date_input):
    """
    Converts a date from datetime object or various string formats to 'YYYY-MM-DD' format.
    Supports formats like:
    - December 01, 2026
    - 2026-12-01
    - 01/12/2026
    """
    if not date_input or str(date_input).strip().lower() in ["n/a", "none", "-", ""]:
        return None

    # Handle datetime objects directly (Excel case)
    if isinstance(date_input, (datetime, pd.Timestamp, date)):
        return date_input.strftime("%Y-%m-%d")

    # Handle string input with multiple formats
    date_str = str(date_input).strip()

    formats_to_try = [
        "%B %d, %Y", # "December 01, 2026" (The one causing your error)
        "%b %d, %Y", # "Dec 01, 2026"
        "%Y-%m-%d",  # ISO format
        "%m/%d/%Y",  # US style
        "%d/%m/%Y",  # European style
        "%d-%m-%Y",  # Common hyphenated
        "%d-%m-%y",  # Short year, like 01-12-27
    ]

    for fmt in formats_to_try:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            # Special handling: if year is two digits (like 27), assume it's 2027 not 1927
            if date_obj.year < 100:
                date_obj = date_obj.replace(year=date_obj.year + 2000)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None  # Fallback if all parsing fails


# ==========================================
# Progress helpers (cache)
# ==========================================

def progress_get(task_id: Optional[str]):
    if not task_id:
        return {"status": "pending", "progress": 0}
    return cache.get(task_id, {"status": "pending", "progress": 0})


def progress_set_processing(task_id: str, *, index: int, total_rows: int, every: int = 10, timeout: int = 300):
    if total_rows <= 0:
        cache.set(task_id, {"status": "processing", "progress": 0}, timeout=timeout)
        return

    if index % every == 0 or index == total_rows - 1:
        progress = int(((index + 1) / total_rows) * 100)
        cache.set(task_id, {"status": "processing", "progress": progress}, timeout=timeout)


def progress_set_completed(task_id: str, timeout: int = 300):
    cache.set(task_id, {"status": "completed", "progress": 100}, timeout=timeout)


def progress_set_error(task_id: str, error: str, timeout: int = 300):
    cache.set(task_id, {"status": "error", "error": error}, timeout=timeout)


# ==========================================
# File validation helpers
# ==========================================

def validate_csv_file_or_response(csv_file):
    """
    Returns:
      - JsonResponse (error) if invalid
      - None if valid
    """
    if not csv_file:
        return None 

    if not csv_file.name.lower().endswith(".csv"):
        return JsonResponse(
            {"error": "Invalid file format. Please upload a CSV file only."},
            status=400
        )

    return None


# ==========================================
# CSV reading + row normalization
# ==========================================

def read_csv_rows(file_path: str) -> List[Dict[str, Any]]:
    with default_storage.open(file_path) as f:
        content = f.read().decode("utf-8-sig")

    reader = csv.DictReader(StringIO(content))
    return list(reader)


def normalize_row(row: Dict[str, Any]) -> Dict[str, str]:
    return {
        str(k).strip(): str(v).strip() if pd.notnull(v) else ""
        for k, v in row.items()
    }