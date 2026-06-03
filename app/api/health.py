from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter

from app.core.config import get_settings
from app.db.session import check_database_connection


router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    version: str


class ReadinessResponse(HealthResponse):
    database: str
    signaling: str
    max_participants_per_meeting: int


@router.get("/health/live", response_model=HealthResponse)
def live_health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness_health() -> ReadinessResponse:
    settings = get_settings()
    check_database_connection()
    return ReadinessResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
        database="ok",
        signaling="ok",
        max_participants_per_meeting=settings.max_participants_per_meeting,
    )


@router.get("/health", response_model=HealthResponse, deprecated=True)
def legacy_health() -> HealthResponse:
    return live_health()
