# ToP/utils/sales_performance_utils.py

from __future__ import annotations

from typing import Dict, Any
from django.db.models import Q


PREMIUM_FIELD_MAPPING: Dict[str, str] = {
    "main_view": "main_view",
    "secondary_view": "secondary_view",
    "north_breeze": "north_breeze",
    "corners": "corners",
    "accessibility": "accessibility",
    "special_premiums": "special_premiums",
    "special_discounts": "special_discounts",
}


def build_status_counts(qs, price_mode: bool = False) -> Dict[str, int]:
    """
    Preserves your exact status logic:
    - released = Available or Contracted
    - available = Available
    - sold_booked = Contracted

    price_mode is only to keep naming consistent; logic is identical.
    """
    all_count = qs.count()
    released_count = qs.filter(Q(status="Available") | Q(status="Contracted") | Q(status="Reserved")).count()
    available_count = qs.filter(status="Available").count()
    sold_booked_count = qs.filter(status="Contracted").count()

    return {
        "all": all_count,
        "released": released_count,
        "available": available_count,
        "sold_booked": sold_booked_count,
    }


def attach_percentages(rows: list[Dict[str, Any]], total_all: int) -> None:
    """
    Preserves your percent formulas:
    - breakdown_percent = all / total_all * 100
    - released_percent = released / total_all * 100
    """
    for row in rows:
        row["breakdown_percent"] = (row.get("all", 0) / total_all * 100) if total_all > 0 else 0
        row["released_percent"] = (row.get("released", 0) / total_all * 100) if total_all > 0 else 0
