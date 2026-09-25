"""Общие фикстуры: 4 сервиса в одном процессе, SQLite + InMemoryEventBus + ASGI-транспорты."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from catalog_app.core.database import Base as CatalogBase
from catalog_app.main import create_app as create_catalog_app
from gateway_app.main import create_app as create_gateway_app
from notification_app.core.database import Base as NotificationBase
from notification_app.main import _make_order_created_handler
from notification_app.main import create_app as create_notification_app
from order_app.core.catalog_client import CatalogClient, CatalogUnavailableError
from order_app.core.database import Base as OrderBase
from order_app.core.resilience import CircuitBreaker
from order_app.main import create_app as create_order_app
from shared.contracts import TOPIC_ORDER_CREATED, ProductRead
from shared.events import InMemoryEventBus


async def make_session_factory(
    base: type,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


class UnavailableCatalog:
    """Заглушка catalog-service: всегда недоступен (контур разомкнут)."""

    async def get_product(self, product_id: int) -> ProductRead:
        raise CatalogUnavailableError(f"product {product_id}: catalog is down")

    async def aclose(self) -> None:
        return None


@dataclass
class Env:
    catalog_app: Any
    order_app: Any
    degraded_order_app: Any
    notification_app: Any
    gateway_app: Any
    bus: InMemoryEventBus

    def client_for(self, app: Any, base_url: str = "http://test") -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=base_url)

    def catalog_transport(self) -> httpx.ASGITransport:
        return httpx.ASGITransport(app=self.catalog_app)


@pytest.fixture
async def env() -> AsyncIterator[Env]:
    engines: list[AsyncEngine] = []

    catalog_engine, catalog_factory = await make_session_factory(CatalogBase)
    engines.append(catalog_engine)
    catalog_app = create_catalog_app(session_factory=catalog_factory)

    order_engine, order_factory = await make_session_factory(OrderBase)
    engines.append(order_engine)

    notification_engine, notification_factory = await make_session_factory(NotificationBase)
    engines.append(notification_engine)

    bus = InMemoryEventBus()
    notification_app = create_notification_app(session_factory=notification_factory, bus=bus)
    await bus.subscribe(TOPIC_ORDER_CREATED, _make_order_created_handler(notification_app))

    catalog_client = CatalogClient(
        "http://catalog",
        transport=httpx.ASGITransport(app=catalog_app),
        breaker=CircuitBreaker(failure_threshold=3, recovery_timeout=30.0),
        max_attempts=2,
        wait_multiplier=0.01,
    )
    order_app = create_order_app(
        session_factory=order_factory, bus=bus, catalog_client=catalog_client
    )
    degraded_order_app = create_order_app(
        session_factory=order_factory,
        bus=bus,
        catalog_client=UnavailableCatalog(),  # type: ignore[arg-type]
    )

    gateway_app = create_gateway_app(
        transports={
            "catalog": httpx.ASGITransport(app=catalog_app),
            "order": httpx.ASGITransport(app=order_app),
            "notification": httpx.ASGITransport(app=notification_app),
        }
    )

    yield Env(
        catalog_app=catalog_app,
        order_app=order_app,
        degraded_order_app=degraded_order_app,
        notification_app=notification_app,
        gateway_app=gateway_app,
        bus=bus,
    )

    await catalog_client.aclose()
    await bus.close()
    for engine in engines:
        await engine.dispose()


@pytest.fixture
async def catalog_client(env: Env) -> AsyncIterator[httpx.AsyncClient]:
    async with env.client_for(env.catalog_app, "http://catalog") as client:
        yield client


@pytest.fixture
async def order_client(env: Env) -> AsyncIterator[httpx.AsyncClient]:
    async with env.client_for(env.order_app, "http://order") as client:
        yield client


@pytest.fixture
async def notification_client(env: Env) -> AsyncIterator[httpx.AsyncClient]:
    async with env.client_for(env.notification_app, "http://notification") as client:
        yield client


@pytest.fixture
async def gateway(env: Env) -> AsyncIterator[httpx.AsyncClient]:
    async with env.client_for(env.gateway_app, "http://gateway") as client:
        yield client


PRODUCT: dict[str, Any] = {"sku": "SKU-1", "name": "Desk Lamp", "price": 1500.0, "stock": 5}


async def create_product(client: httpx.AsyncClient, **overrides: Any) -> dict[str, Any]:
    resp = await client.post("/api/v1/products", json={**PRODUCT, **overrides})
    assert resp.status_code == 201, resp.text
    return resp.json()
