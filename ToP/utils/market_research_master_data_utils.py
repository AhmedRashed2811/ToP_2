# ToP/utils/market_research_master_data_utils.py

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type

from django.http import HttpRequest


@dataclass
class ParsedJson:
    ok: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def parse_json_body(body: bytes) -> ParsedJson:
    """Parse request.body safely. Returns ParsedJson(ok, data/error)."""
    try:
        if not body:
            return ParsedJson(ok=False, error="Empty body")
        return ParsedJson(ok=True, data=json.loads(body))
    except Exception:
        return ParsedJson(ok=False, error="Invalid JSON body")


def decode_csv_file_to_lines(file_bytes: bytes) -> Tuple[Optional[List[str]], Optional[str]]:
    """
    Decode CSV bytes using fallback encodings (preserved list).
    Returns (lines, error).
    """
    encodings_to_try = ["utf-8-sig", "utf-8", "latin1", "cp1252"]
    for enc in encodings_to_try:
        try:
            lines = file_bytes.decode(enc).splitlines()
            return lines, None
        except UnicodeDecodeError:
            continue
    return None, "Unsupported file encoding"


def require_keys(payload: Dict[str, Any], keys: Iterable[str]) -> Tuple[bool, Optional[str]]:
    """Validate required keys exist and are truthy (not None/empty)."""
    for k in keys:
        if payload.get(k) in (None, ""):
            return False, f"Missing required field: {k}"
    return True, None
