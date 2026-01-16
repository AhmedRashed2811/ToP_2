# ToP/utils/modification_records_utils.py

from typing import Iterable, List, TypeVar

T = TypeVar("T")


def unique_preserve_order(items: Iterable[T]) -> List[T]:
    """
    Returns a list of unique items while preserving first-seen order.
    """
    seen = set()
    out: List[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
