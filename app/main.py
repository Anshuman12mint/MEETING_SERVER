from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import configure_security
from app.db.migrations import upgrade_database
from app.db.session import dispose_database_engine, initialize_database


configure_logging(force=True)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("application_starting env=%s version=%s", settings.app_env, settings.app_version)
    if settings.run_migrations_on_startup:
        logger.info("database_migrations_starting")
        upgrade_database("head")
    elif settings.auto_initialize_schema:
        logger.warning("database_schema_auto_initialization_enabled")
        initialize_database()
    try:
        yield
    finally:
        logger.info("application_stopping")
        dispose_database_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )
    configure_security(app)
    app.include_router(api_router)
    return app


app = create_app()
