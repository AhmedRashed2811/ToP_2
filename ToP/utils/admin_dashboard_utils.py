# ToP/utils/admin_dashboard_utils.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Type

from django.apps import apps
from django.db import models
from django.db.models import Q


# ================= SECURITY CHECK =================
def is_superuser_check(user) -> bool:
    """
    Strict security check.
    Returns True ONLY if the user is logged in AND is a Superuser.
    """
    return bool(user and user.is_authenticated and user.is_superuser)


# ================= GLOBAL SENSITIVE FIELDS =================
# These fields will be hidden from ALL forms to prevent critical account takeovers.
GLOBAL_SENSITIVE_FIELDS: List[str] = [
    # Add anything you want to always hide globally, e.g.:
    # "password", "is_superuser", "user_permissions", "groups",
]


# ================= CUSTOMIZATION (OVERRIDES) =================
MODEL_OVERRIDES: Dict[str, Dict] = {
    "user": {
        "list_display": ["email", "full_name", "role", "joining_date", "is_active"],
        "search_fields": ["email", "full_name"],
        "can_delete": False,
    },
    "salesrequest": {
        "list_display": ["sales_man", "unit", "client_name", "final_price", "is_approved"],
        "search_fields": ["client_name", "client_id"],
    },
    "salesrequestanalytical": {
        "list_display": ["sales_man", "unit", "client_name", "final_price", "date", "is_approved"],
        "can_create": False,
    },
    "unit": {
        "list_display": ["unit_code", "project", "unit_type", "final_price", "status"],
        "search_fields": ["unit_code", "sap_code"],
    },
}


@dataclass(frozen=True)
class ModelDashboardConfig:
    model: Type[models.Model]
    list_display: List[str]
    search_fields: List[str]
    exclude_fields: List[str]
    can_create: bool
    can_delete: bool


def get_all_top_models(app_label: str = "ToP") -> List[str]:
    return [m._meta.model_name for m in apps.get_app_config(app_label).get_models()]


def safe_model_count(model: Type[models.Model]) -> int:
    try:
        return model.objects.count()
    except Exception:
        return 0


def get_model_config(app_label: str, model_name: str) -> Tuple[Optional[Type[models.Model]], Optional[ModelDashboardConfig]]:
    """
    Returns (model_class, config) or (None, None) if not found.
    Preserves your override + fallback behavior.
    """
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return None, None

    model_name_lower = model_name.lower()
    override = MODEL_OVERRIDES.get(model_name_lower, {})

    # Default list_display behavior (same idea as your original):
    # take first 5 non-auto-created fields.
    default_list_display = [
        f.name for f in model._meta.fields if not getattr(f, "auto_created", False)
    ][:5]

    list_display = override.get("list_display", default_list_display)
    search_fields = override.get("search_fields", [])

    exclude_fields = GLOBAL_SENSITIVE_FIELDS + override.get("exclude_fields", [])
    can_create = override.get("can_create", True)
    can_delete = override.get("can_delete", True)

    return model, ModelDashboardConfig(
        model=model,
        list_display=list_display,
        search_fields=search_fields,
        exclude_fields=exclude_fields,
        can_create=can_create,
        can_delete=can_delete,
    )


def build_search_q(model: Type[models.Model], query: str, search_fields: List[str]) -> Q:
    """
    Same logic:
    - If search_fields empty: auto-detect Char/Text/Email fields and search them.
    - Else search in the configured fields.
    """
    q_obj = Q()

    if not query:
        return q_obj

    if not search_fields:
        for field in model._meta.fields:
            if isinstance(field, (models.CharField, models.TextField, models.EmailField)):
                q_obj |= Q(**{f"{field.name}__icontains": query})
    else:
        for f in search_fields:
            q_obj |= Q(**{f"{f}__icontains": query})

    return q_obj
