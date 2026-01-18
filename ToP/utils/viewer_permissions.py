# ToP/utils/viewer_permissions.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Set


# -----------------------------
# 1) Canonical page slugs
# -----------------------------
PAGE_INV_REPORT = "inv_report"
PAGE_MASTERPLANS = "masterplans"
PAGE_CATALOG = "catalog"
PAGE_ToP = "top" 
PAGE_SALES_PERFORMANCE_ANALYSIS = "SPA"

# "What admin types in JSON" -> canonical slug
_PAGE_ALIASES = {
    PAGE_INV_REPORT: {"inv report", "inventory report", "inv_report", "Inventory Report"},
    PAGE_MASTERPLANS: {"Masterplan", "masterplans", "masterplan", "unit mapping", "mapping", "unit_mapping", "unit mapping read only"},
    PAGE_CATALOG: {"catalog", "unit catalog", "unit_catalog"},
    PAGE_ToP:{"top"},
    PAGE_SALES_PERFORMANCE_ANALYSIS:{"sales performance analysis", "spa"}
    
} 

# -----------------------------
# 2) Allowed unit statuses
# -----------------------------
ALLOWED_VIEWER_STATUSES = {
    "Available",
    "Reserved",
    "Contracted",
    "Blocked Development",
    "Partner",
    "Hold",
    "Blocked Sales",
}

# normalize for comparisons
_ALLOWED_STATUS_NORM = {s.lower(): s for s in ALLOWED_VIEWER_STATUSES}


def _norm_token(x: Any) -> str:
    return str(x or "").strip().lower()


def is_company_viewer(user) -> bool:
    # Your model uses related_name='viewer_profile'
    return hasattr(user, "viewer_profile") and getattr(user, "viewer_profile", None) is not None


def _read_allowed_list(user) -> list:
    """
    Supports:
      - allowed_pages as a list (your current design)
      - OR dict future-proofing: {"pages": [...], "statuses": [...]}
    """
    if not is_company_viewer(user):
        return []

    raw = getattr(user.viewer_profile, "allowed_pages", None)

    if isinstance(raw, dict):
        pages = raw.get("pages", []) or []
        statuses = raw.get("statuses", []) or []
        return list(pages) + list(statuses)

    if isinstance(raw, list):
        return raw

    return []


def viewer_allowed_pages(user) -> Set[str]:
    """
    Returns canonical page slugs the viewer can access.
    """
    if not is_company_viewer(user):
        return set()

    tokens = {_norm_token(x) for x in _read_allowed_list(user)}
    allowed: Set[str] = set()

    for slug, aliases in _PAGE_ALIASES.items():
        if any(a in tokens for a in aliases):
            allowed.add(slug)

    return allowed


def viewer_allowed_statuses(user) -> Set[str]:
    """
    Returns canonical status names the viewer is allowed to see (e.g. "Available").
    If viewer has none, result is empty -> they see no units/pins.
    """
    if not is_company_viewer(user):
        return set()

    tokens = {_norm_token(x) for x in _read_allowed_list(user)}
    statuses: Set[str] = set()

    for t in tokens:
        if t in _ALLOWED_STATUS_NORM:
            statuses.add(_ALLOWED_STATUS_NORM[t])

    return statuses


def viewer_can_access_page(user, page_slug: str) -> bool:
    """
    Non-viewers: always True.
    Viewers: must have page slug allowed.
    """
    if not is_company_viewer(user):
        return True
    return page_slug in viewer_allowed_pages(user)


def viewer_company(user):
    """
    Non-viewers: None
    Viewers: CompanyViewer.company
    """
    if not is_company_viewer(user):
        return None
    return getattr(user.viewer_profile, "company", None)
