from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import get_settings


logger = logging.getLogger(__name__)
request_logger = logging.getLogger("meeting_server.requests")


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, request_id_header_name: str) -> None:
        super().__init__(app)
        self.request_id_header_name = request_id_header_name

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(self.request_id_header_name) or uuid4().hex
        request.state.request_id = request_id
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started_at) * 1000
            request_logger.exception(
                "request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        response.headers[self.request_id_header_name] = request_id
        request_logger.info(
            "request_completed request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
        return response


def configure_security(app: FastAPI) -> None:
    settings = get_settings()
    if settings.trusted_hosts_list:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts_list)
    app.add_middleware(RequestContextMiddleware, request_id_header_name=settings.request_id_header_name)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[settings.request_id_header_name],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        code = {
            400: "bad_request",
            401: "authentication_required",
            403: "access_denied",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
        }.get(exc.status_code, "request_failed")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.status_code, code, message, request),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        message = exc.errors()[0].get("msg", "Validation failed") if exc.errors() else "Validation failed"
        return JSONResponse(
            status_code=422,
            content=error_payload(422, "validation_error", message, request),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception request_id=%s path=%s", request_id_from(request), request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_payload(500, "internal_server_error", "Internal server error", request),
        )


def request_id_from(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_payload(status_code: int, code: str, message: str, request: Request) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": status_code,
        "code": code,
        "message": message,
    }
    request_id = request_id_from(request)
    if request_id is not None:
        payload["requestId"] = request_id
    return payload
