from __future__ import annotations

from typing import Any

import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings
from app.modules.auth.schemas import AuthenticatedPrincipal


class JwtService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def parse_claims(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self.settings.jwt_secret,
            algorithms=["HS256"],
            audience=self.settings.jwt_audience,
            issuer=self.settings.jwt_issuer,
            leeway=self.settings.jwt_leeway_seconds,
        )

    def parse_principal(self, token: str) -> AuthenticatedPrincipal:
        claims = self.parse_claims(token)
        login_id = str(claims.get("sub") or "").strip()
        role = str(claims.get("role") or "").strip()
        if not login_id:
            raise InvalidTokenError("Token subject is missing")
        if not role:
            raise InvalidTokenError("Token role is missing")
        return AuthenticatedPrincipal(
            login_id=login_id,
            role=role,
            issuer=claims.get("iss"),
            audience=claims.get("aud"),
            issued_at=claims.get("iat"),
            expires_at=claims.get("exp"),
        )
