from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import unittest

from fastapi import HTTPException
import jwt
from jwt import InvalidTokenError

from app.core.config import clear_settings_cache
from app.modules.auth.dependencies import authenticate_token, get_current_principal, require_roles
from app.modules.auth.jwt import JwtService
from app.modules.auth.schemas import AuthenticatedPrincipal


class JwtCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_env = os.environ.copy()
        os.environ.update(
            {
                "APP_ENV": "test",
                "JWT_SECRET": "meeting-test-secret-value",
                "JWT_ISSUER": "college-server",
                "JWT_AUDIENCE": "college-clients",
                "JWT_LEEWAY_SECONDS": "0",
            }
        )
        clear_settings_cache()

    def tearDown(self) -> None:
        clear_settings_cache()
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_parses_college_server_token(self) -> None:
        token = self.make_token(login_id="STU-00001", role="Student")

        principal = JwtService().parse_principal(token)

        self.assertEqual(principal.login_id, "STU-00001")
        self.assertEqual(principal.role, "Student")
        self.assertEqual(principal.issuer, "college-server")
        self.assertEqual(principal.audience, "college-clients")

    def test_rejects_invalid_or_expired_tokens(self) -> None:
        wrong_audience_token = self.make_token(login_id="TCH-00001", role="Teacher", audience="wrong-client")
        expired_token = self.make_token(login_id="TCH-00001", role="Teacher", expires_in_seconds=-10)

        with self.assertRaises(InvalidTokenError):
            JwtService().parse_principal(wrong_audience_token)
        with self.assertRaises(InvalidTokenError):
            JwtService().parse_principal(expired_token)
        self.assertIsNone(authenticate_token(wrong_audience_token))

    def test_requires_authenticated_principal(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            get_current_principal(None)

        self.assertEqual(raised.exception.status_code, 401)

    def test_role_dependency_allows_only_configured_roles(self) -> None:
        teacher = AuthenticatedPrincipal(login_id="TCH-00001", role="Teacher")
        student = AuthenticatedPrincipal(login_id="STU-00001", role="Student")
        teacher_only = require_roles("Teacher", "Admin")

        self.assertEqual(teacher_only(teacher), teacher)
        with self.assertRaises(HTTPException) as raised:
            teacher_only(student)

        self.assertEqual(raised.exception.status_code, 403)

    def make_token(
        self,
        login_id: str,
        role: str,
        issuer: str = "college-server",
        audience: str = "college-clients",
        expires_in_seconds: int = 300,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": login_id,
            "role": role,
            "iss": issuer,
            "aud": audience,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
        }
        return jwt.encode(payload, "meeting-test-secret-value", algorithm="HS256")


if __name__ == "__main__":
    unittest.main()
