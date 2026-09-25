"""Точка входа catalog-service: create_app() + /health."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from catalog_app.api.router import api_router
from catalog_app.core.config import get_settings
from catalog_app.core.database import dispose_engine, get_session_factory
from shared.context import RequestIdMiddleware
from shared.contracts import HealthResponse
from shared.errors import register_exception_handlers
from shared.logs import configure_logging

SERVICE_NAME = "catalog-service"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app(*, session_factory: async_sessionmaker[AsyncSession] | None = None) -> FastAPI:
    settings = get_settings()
    logger = configure_logging(SERVICE_NAME, __name__)
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.state.session_factory = (
        session_factory if session_factory is not None else get_session_factory()
    )
    app.add_middleware(RequestIdMiddleware, logger=logger)
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["health"], response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(service=SERVICE_NAME)

    return app
