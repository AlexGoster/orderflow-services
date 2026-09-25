"""Точка входа order-service: create_app() + /health."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from order_app.api.router import api_router
from order_app.core.catalog_client import CatalogClient
from order_app.core.config import Settings, get_settings
from order_app.core.database import dispose_engine, get_session_factory
from order_app.core.resilience import CircuitBreaker
from shared.context import RequestIdMiddleware
from shared.contracts import HealthResponse
from shared.errors import register_exception_handlers
from shared.events import EventBus, create_event_bus
from shared.logs import configure_logging

SERVICE_NAME = "order-service"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()
    client: CatalogClient = app.state.catalog_client
    await client.aclose()
    bus: EventBus = app.state.bus
    await bus.close()


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    bus: EventBus | None = None,
    catalog_client: CatalogClient | None = None,
) -> FastAPI:
    resolved_settings = settings if settings is not None else get_settings()
    logger = configure_logging(SERVICE_NAME, __name__)
    app = FastAPI(title=resolved_settings.app_name, version="1.0.0", lifespan=lifespan)
    app.state.session_factory = (
        session_factory if session_factory is not None else get_session_factory()
    )
    app.state.bus = (
        bus
        if bus is not None
        else create_event_bus(
            backend=resolved_settings.bus_backend, redis_url=resolved_settings.redis_url
        )
    )
    app.state.catalog_client = (
        catalog_client
        if catalog_client is not None
        else CatalogClient(
            resolved_settings.catalog_service_url,
            timeout=resolved_settings.catalog_timeout,
            max_attempts=resolved_settings.catalog_max_attempts,
            breaker=CircuitBreaker(
                failure_threshold=resolved_settings.catalog_failure_threshold,
                recovery_timeout=resolved_settings.catalog_recovery_timeout,
            ),
        )
    )
    app.add_middleware(RequestIdMiddleware, logger=logger)
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["health"], response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(service=SERVICE_NAME)

    return app
