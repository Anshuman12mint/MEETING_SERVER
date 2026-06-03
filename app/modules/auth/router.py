from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.auth.dependencies import get_current_principal
from app.modules.auth.schemas import AuthenticatedPrincipal


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=AuthenticatedPrincipal)
def me(current_principal: AuthenticatedPrincipal = Depends(get_current_principal)) -> AuthenticatedPrincipal:
    return current_principal
