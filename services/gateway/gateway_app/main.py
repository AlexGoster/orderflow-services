"""Точка входа шлюза: create_app() + /health."""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from gateway_app.api.router import api_router
from gateway_app.core.clients import ServiceClients
from gateway_app.core.config import get_settings
from shared.context import RequestIdMiddleware
from shared.contracts import HealthResponse
from shared.errors import register_exception_handlers
from shared.logs import configure_logging

SERVICE_NAME = "gateway"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    clients: ServiceClients = app.state.clients
    await clients.aclose()


def create_app(
    *,
    transports: Mapping[str, httpx.AsyncBaseTransport] | None = None,
) -> FastAPI:
    settings = get_settings()
    logger = configure_logging(SERVICE_NAME, __name__)
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.state.clients = ServiceClients(settings, transports=transports)
    app.add_middleware(RequestIdMiddleware, logger=logger)
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["health"], response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(service=SERVICE_NAME)

    return app
