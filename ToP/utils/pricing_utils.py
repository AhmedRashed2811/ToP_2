# ToP/utils/pricing_utils.py

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from django.db import models

from ..models import Unit


# ----------------------------
# Numeric / Decimal parsing
# ----------------------------
def parse_optional_decimal(raw: Optional[str]) -> Optional[Decimal]:
    """
    Matches your current behavior:
    - None / '' / 'null' / 'undefined' => None
    - else Decimal(str(raw)) or raises InvalidOperation/ValueError
    """
    if raw in [None, "", "null", "undefined"]:
        return None
    return Decimal(str(raw))


# ----------------------------
# Rounding behavior
# ----------------------------
def roundup_to_nearest_ten(value: Optional[Decimal]) -> Optional[Decimal]:
    """
    Same as your _roundup_to_nearest_ten:
    - None => None
    - 0 => Decimal('0')
    - otherwise roundup to nearest 10 using ROUND_CEILING
    """
    if value is None:
        return None
    if value == 0:
        return Decimal("0")
    ten = Decimal("10")
    q = (value / ten).to_integral_value(rounding=ROUND_CEILING)
    return q * ten


# ----------------------------
# Model field inspection
# ----------------------------
def unit_field_names() -> Set[str]:
    return {f.name for f in Unit._meta.get_fields() if hasattr(f, "name")}


def first_existing_field(candidate_names: Sequence[str]) -> Optional[str]:
    names = unit_field_names()
    for f in candidate_names:
        if f in names:
            return f
    return None


# ----------------------------
# Positive area checks (same queries, only extracted)
# ----------------------------
def unit_has_positive_field(project_obj, unit_model: str, field_name: str) -> bool:
    """
    Generic helper used by specific wrappers below.
    Mirrors your query logic exactly:
    - filter by project name, company, unit_model
    - exclude field None
    - field__gt 0
    """
    return (
        Unit.objects.filter(
            project=project_obj.name,
            company=project_obj.company,
            unit_model=unit_model,
        )
        .exclude(**{field_name: None})
        .filter(**{f"{field_name}__gt": 0})
        .exists()
    )


def unit_has_positive_penthouse(project_obj, unit_model: str) -> bool:
    ph_field = first_existing_field(["penthouse", "penthouse_area"])
    if not ph_field:
        return False
    return unit_has_positive_field(project_obj, unit_model, ph_field)


def unit_has_positive_roof(project_obj, unit_model: str) -> bool:
    roof_field = first_existing_field(["roof_area", "roof_terraces_area"])
    if not roof_field:
        return False
    return unit_has_positive_field(project_obj, unit_model, roof_field)


def unit_has_positive_land(project_obj, unit_model: str) -> bool:
    land_field = first_existing_field(["land_area", "garden_area"])
    if not land_field:
        return False
    return unit_has_positive_field(project_obj, unit_model, land_field)


# ----------------------------
# Dynamic Unit fields list builder (same behavior)
# ----------------------------
def build_unit_values_fields() -> List[str]:
    """
    Rebuilds the exact base_fields logic from your view, plus optional fields.
    """
    base_fields = [
        "unit_code", "main_view", "secondary_views", "levels", "north_breeze",
        "corners", "accessibility", "special_premiums", "special_discounts",
        "phasing", "base_price", "internal_area", "unit_model", "status",
        "unit_type", "building_number", "building_type", "city", "floor",
        "status", "gross_area",
    ]

    names = unit_field_names()

    # Optional fields (exact same conditionals)
    if "covered_terrace" in names:
        base_fields.append("covered_terrace")
    if "roof_area" in names:
        base_fields.append("roof_area")
    if "roof_terraces_area" in names:
        base_fields.append("roof_terraces_area")
    if "land_area" in names:
        base_fields.append("land_area")
    if "garden_area" in names:
        base_fields.append("garden_area")

    ph_field = None
    if "penthouse" in names:
        ph_field = "penthouse"
    elif "penthouse_area" in names:
        ph_field = "penthouse_area"
    if ph_field:
        base_fields.append(ph_field)

    return base_fields


# ----------------------------
# Mapping: group name -> Unit field
# ----------------------------
DEFAULT_GROUP_TO_FIELD_MAPPING: Dict[str, str] = {
    "main view": "main_view",
    "secondary views": "secondary_views",
    "levels": "levels",
    "north breeze": "north_breeze",
    "corners": "corners",
    "accessibility": "accessibility",
    "special premiums": "special_premiums",
    "special discounts": "special_discounts",
    "phasing": "phasing",
}


def normalize_group_name(name: str) -> str:
    return (name or "").lower().strip()
