from __future__ import annotations

from fastapi import HTTPException, status


def has_text(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def require_text(value: str | None, field_name: str) -> None:
    require(has_text(value), f"{field_name} is required")
