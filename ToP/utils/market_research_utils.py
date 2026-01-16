# ToP/utils/market_research_utils.py

from __future__ import annotations

from typing import Any, Dict

from ..models import CompanyManager


# ----------------------------------------------
# Base template + (Manager -> company) helper
# ----------------------------------------------
def build_base_context(user) -> Dict[str, Any]:
    """
    Preserves your repeated logic:
    - authenticated => ToP/base.html
    - guest => ToP/guest_base.html
    - if user is in "Manager" group => attach company to context["company"]
    """
    context: Dict[str, Any] = {}

    if getattr(user, "is_authenticated", False):
        context["base_template"] = "ToP/base.html"

        try:
            if user.groups.filter(name="Manager").exists():
                manager = CompanyManager.objects.filter(user=user).first()
                if manager and manager.company:
                    context["company"] = manager.company
        except Exception:
            # Don’t break pages if group/manager model has issues
            pass
    else:
        context["base_template"] = "ToP/guest_base.html"

    return context


# ----------------------------------------------
# Format numbers for display (your util)
# ----------------------------------------------
def format_number(value: Any) -> str:
    """Format numbers for display"""
    if value is None:
        return "0"
    try:
        value = float(value)
    except (ValueError, TypeError):
        return "0"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    elif value >= 1_000:
        return f"{value / 1_000:.1f}K"
    else:
        return f"{value:.0f}"


# ----------------------------------------------
# Range formatter (used by project cards)
# ----------------------------------------------
def format_range(min_val: Any, max_val: Any, suffix: str = "") -> str:
    """
    Converts min/max to readable range using format_number:
    - None/None => "N/A"
    - equal => "<val><suffix>"
    - range => "<min><suffix> - <max><suffix>"
    """
    if min_val is None and max_val is None:
        return "N/A"
    if min_val == max_val:
        return f"{format_number(min_val)}{suffix}"
    return f"{format_number(min_val)}{suffix} - {format_number(max_val)}{suffix}"


# ----------------------------------------------
# Extract filters from request parameters (validated)
# ----------------------------------------------
def get_filters_from_request(request) -> Dict[str, Any]:
    """
    Extract filters from GET request params.
    Matches your view usage (developers[], locations[], etc.).
    Keeps numeric filters as raw values (strings) to preserve old apply_filters logic.
    """
    return {
        "developers": request.GET.getlist("developers[]", []),
        "locations": request.GET.getlist("locations[]", []),
        "asset_types": request.GET.getlist("asset_types[]", []),
        "unit_types": request.GET.getlist("unit_types[]", []),
        "finishing_specs": request.GET.getlist("finishing_specs[]", []),
        "min_price": request.GET.get("min_price", None),
        "max_price": request.GET.get("max_price", None),
        "min_bua": request.GET.get("min_bua", None),
        "max_bua": request.GET.get("max_bua", None),
        "payment_years": request.GET.getlist("payment_years[]", []),
    }


# ---------------------------------------------- Apply filters to queryset (your helper)
def apply_filters(queryset, filters):
    """Apply filters to queryset"""
    if filters["developers"]:
        queryset = queryset.filter(developer_name__in=filters["developers"])

    if filters["locations"]:
        queryset = queryset.filter(location__in=filters["locations"])

    if filters["asset_types"]:
        queryset = queryset.filter(asset_type__in=filters["asset_types"])

    if filters["unit_types"]:
        queryset = queryset.filter(unit_type__in=filters["unit_types"])

    if filters["finishing_specs"]:
        queryset = queryset.filter(finishing_specs__in=filters["finishing_specs"])

    if filters["min_price"]:
        try:
            queryset = queryset.filter(unit_price__gte=float(filters["min_price"]))
        except (ValueError, TypeError):
            pass

    if filters["max_price"]:
        try:
            queryset = queryset.filter(unit_price__lte=float(filters["max_price"]))
        except (ValueError, TypeError):
            pass

    if filters["min_bua"]:
        try:
            queryset = queryset.filter(bua__gte=float(filters["min_bua"]))
        except (ValueError, TypeError):
            pass

    if filters["max_bua"]:
        try:
            queryset = queryset.filter(bua__lte=float(filters["max_bua"]))
        except (ValueError, TypeError):
            pass

    if filters["payment_years"]:
        queryset = queryset.filter(payment_yrs__in=filters["payment_years"])

    return queryset
