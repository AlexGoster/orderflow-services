"""Точка входа notification-service: create_app(), /health и подписка на шину."""

import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from notification_app.api.router import api_router
from notification_app.core.config import Settings, get_settings
from notification_app.core.database import dispose_engine, get_session_factory
from notification_app.services import notifications as notifications_service
from shared.context import RequestIdMiddleware
from shared.contracts import TOPIC_ORDER_CREATED, HealthResponse, OrderCreated
from shared.errors import register_exception_handlers
from shared.events import EventBus, EventHandler, create_event_bus
from shared.logs import configure_logging

SERVICE_NAME = "notification-service"

logger = logging.getLogger(__name__)


def _make_order_created_handler(app: FastAPI) -> EventHandler:
    async def handler(payload: Mapping[str, Any]) -> None:
        try:
            event = OrderCreated.model_validate(payload)
        except ValidationError as exc:
            logger.error("invalid order.created payload", extra={"error": str(exc)})
            return
        factory: async_sessionmaker[AsyncSession] = app.state.session_factory
        async with factory() as session:
            await notifications_service.send_order_notification(session, event)

    return handler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    bus: EventBus = app.state.bus
    await bus.subscribe(TOPIC_ORDER_CREATED, _make_order_created_handler(app))
    logger.info("subscribed to topic", extra={"topic": TOPIC_ORDER_CREATED})
    yield
    await bus.close()
    await dispose_engine()


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    bus: EventBus | None = None,
) -> FastAPI:
    resolved_settings = settings if settings is not None else get_settings()
    pkg_logger = configure_logging(SERVICE_NAME, __name__)
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
    app.add_middleware(RequestIdMiddleware, logger=pkg_logger)
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["health"], response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(service=SERVICE_NAME)

    return app
