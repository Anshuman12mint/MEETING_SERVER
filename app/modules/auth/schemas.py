from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuthenticatedPrincipal(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    login_id: str = Field(serialization_alias="loginId")
    role: str
    issuer: str | None = None
    audience: str | list[str] | None = None
    issued_at: int | None = Field(default=None, serialization_alias="issuedAt")
    expires_at: int | None = Field(default=None, serialization_alias="expiresAt")
