import re
from typing import Any, Dict


def normalize_header(name: Any) -> str:
    """
    Makes matching resilient:
    - trims
    - lowers
    - converts spaces/dashes to underscore
    - removes repeated underscores
    """
    s = str(name or "").strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s


def apply_header_mapping(item: Any, mapping: Dict[str, str]) -> Any:
    """
    Recursively applies mapping to dict keys.
    mapping is expected to be {provided_name: needed_name}
    Matching is done with normalize_header on both sides.
    """
    if not mapping:
        return item

    normalized_map = {normalize_header(k): v for k, v in mapping.items()}

    if isinstance(item, dict):
        out = {}
        for k, v in item.items():
            nk = normalize_header(k)
            target_key = normalized_map.get(nk, k)  # keep original if not mapped
            # recurse for nested dict/list
            out[target_key] = apply_header_mapping(v, mapping) if isinstance(v, (dict, list)) else v
        return out

    if isinstance(item, list):
        return [apply_header_mapping(x, mapping) for x in item]

    return item
