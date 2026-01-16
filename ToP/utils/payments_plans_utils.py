# ToP/utils/payments_plans_utils.py

from __future__ import annotations

from typing import Dict, Any, List, Tuple


INSTALLMENTS_COUNT = 48  # you use installment_1 .. installment_48
CUMULATIVES_COUNT = 48   # you use cumulative_1 .. cumulative_48


def normalize_updates(payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Preserves your original behavior:
    - if bulk_updates is present and list -> use it
    - else fallback to single update with index/value
    - return (updates_list, has_bulk)
    """
    if "bulk_updates" in payload and isinstance(payload["bulk_updates"], list):
        return payload["bulk_updates"], True

    # fallback single update
    return [
        {
            "index": int(payload.get("index", -1)),
            "value": float(payload.get("value", 0) or 0),
        }
    ], False


def apply_dual_payment_updates(model_obj, updates: List[Dict[str, Any]]) -> None:
    """
    Apply all updates to model_obj in memory (no save).
    Preserves your mapping:
      index 0 -> dp1
      index 1 -> dp2
      index >=2 -> installment_(index-1)  (so index 2 -> installment_1)
    Values are stored as decimals (value/100).
    """
    for item in updates:
        index = int(item.get("index", -1))
        if index < 0:
            continue

        value = float(item.get("value", 0) or 0) / 100.0

        if index == 0:
            model_obj.dp1 = value
        elif index == 1:
            model_obj.dp2 = value
        else:
            setattr(model_obj, f"installment_{index - 1}", value)


def recalc_dual_cumulatives(model_obj) -> None:
    """
    Preserves your cumulative logic exactly:
      cumulative_dp1 = dp1
      cumulative_dp2 = dp1 + dp2
      cumulative_i = dp1+dp2+sum(installment_1..installment_i)
    """
    dp1 = model_obj.dp1 or 0
    dp2 = model_obj.dp2 or 0

    model_obj.cumulative_dp1 = dp1
    model_obj.cumulative_dp2 = dp1 + dp2

    cum = dp1 + dp2
    for i in range(1, CUMULATIVES_COUNT + 1):
        val = getattr(model_obj, f"installment_{i}", 0) or 0
        cum += val
        setattr(model_obj, f"cumulative_{i}", cum)
