from __future__ import annotations

import re


def trim_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def normalize_code(value: str | None) -> str | None:
    trimmed = trim_to_none(value)
    if trimmed is None:
        return None
    return re.sub(r"\s+", "", trimmed).upper()
