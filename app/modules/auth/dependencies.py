from __future__ import annotations

from collections.abc import Callable
import logging

from fastapi import Depends, HTTPException, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError

from app.modules.auth.jwt import JwtService
from app.modules.auth.schemas import AuthenticatedPrincipal


bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def authenticate_token(token: str | None) -> AuthenticatedPrincipal | None:
    if not token:
        return None
    try:
        return JwtService().parse_principal(token.strip())
    except InvalidTokenError:
        logger.warning("token_validation_failed")
        return None


def get_optional_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedPrincipal | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return authenticate_token(credentials.credentials)


def get_current_principal(
    current_principal: AuthenticatedPrincipal | None = Depends(get_optional_current_principal),
) -> AuthenticatedPrincipal:
    if current_principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    return current_principal


def require_roles(*roles: str) -> Callable:
    normalized_roles = {role.strip().upper() for role in roles}

    def dependency(current_principal: AuthenticatedPrincipal = Depends(get_current_principal)) -> AuthenticatedPrincipal:
        if current_principal.role.strip().upper() not in normalized_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access is denied")
        return current_principal

    return dependency


def authenticate_websocket_token(token: str | None) -> AuthenticatedPrincipal:
    principal = authenticate_token(token)
    if principal is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication is required")
    return principal
