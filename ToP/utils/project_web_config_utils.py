# ToP/utils/project_web_config_utils.py

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Dict, List


# ----------------------------------------------
# Convert ints/floats/strings to Decimal or return None for "", "-", None.
def to_decimal_or_none(val: Any) -> Optional[Decimal]:
    """
    Safe Decimal parser:
    - None, "", "-" => None
    - "1,234.56" => Decimal("1234.56")
    - int/float => Decimal(str(val)) (avoid float binary issues)
    """
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))

    s = str(val).strip()
    if s in {"", "-"}:
        return None

    try:
        s = s.replace(",", "")
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


# ----------------------------------------------
# Convert to int or None
def to_int_or_none(val: Any) -> Optional[int]:
    if val in (None, ""):
        return None
    try:
        return int(val)
    except Exception:
        return None


# ----------------------------------------------
# Boolean from POST (checkboxes)
def post_bool(post_dict: Dict[str, Any], key: str) -> bool:
    """
    Mirrors your previous behavior: bool(request.POST.get("field"))
    In Django POST:
      - checked checkbox => "on"
      - unchecked => missing (None)
    """
    return bool(post_dict.get(key))


# ----------------------------------------------
# Optional numeric strings (store None if empty)
def post_optional_str(post_dict: Dict[str, Any], key: str) -> Optional[str]:
    v = post_dict.get(key)
    if v in (None, ""):
        return None
    return str(v)


# ----------------------------------------------
# Safe list getter from POST-like dict
def post_list(post_dict: Dict[str, Any], key: str) -> List[str]:
    """
    Works with request.POST.getlist('payment_schemes')
    In views, pass getlist result to service directly if you want.
    This is mainly for consistent typing.
    """
    v = post_dict.get(key)
    if v is None:
        return []
    if isinstance(v, list):
        return v
    # fallback: single value
    return [str(v)]
