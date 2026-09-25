"""Создание заказа и публикация события order.created."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from order_app.core.catalog_client import CatalogClient, CatalogUnavailableError
from order_app.models import Order, OrderItem
from shared.contracts import (
    TOPIC_ORDER_CREATED,
    OrderCreate,
    OrderCreated,
    OrderItemRead,
    OrderStatus,
)
from shared.errors import NotFoundError
from shared.events import EventBus

logger = logging.getLogger(__name__)


async def create_order(
    session: AsyncSession,
    *,
    payload: OrderCreate,
    catalog: CatalogClient,
    request_id: str,
) -> Order:
    """Проверяет товары в catalog-service; при недоступности сервиса — degraded."""
    lines: list[OrderItem] = []
    warnings: list[str] = []
    degraded = False

    for item in payload.items:
        try:
            product = await catalog.get_product(item.product_id)
        except CatalogUnavailableError as exc:
            degraded = True
            warnings.append(f"product {item.product_id}: {exc}")
            lines.append(
                OrderItem(
                    product_id=item.product_id,
                    name="",
                    quantity=item.quantity,
                    unit_price=Decimal("0"),
                )
            )
            continue
        lines.append(
            OrderItem(
                product_id=product.id,
                name=product.name,
                quantity=item.quantity,
                unit_price=product.price,
            )
        )

    if degraded:
        warnings.insert(0, "catalog-service unavailable: prices and stock were not verified")

    order = Order(
        customer=payload.customer,
        status=OrderStatus.created,
        degraded=degraded,
        warnings=warnings,
        total=sum((line.unit_price * line.quantity for line in lines), Decimal("0")),
        request_id=request_id,
        items=lines,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    logger.info(
        "order created",
        extra={"order_id": order.id, "degraded": order.degraded, "total": str(order.total)},
    )
    return order


async def publish_order_created(bus: EventBus, order: Order) -> None:
    event = OrderCreated(
        event_id=uuid4(),
        order_id=order.id,
        customer=order.customer,
        degraded=order.degraded,
        total=order.total,
        items=[OrderItemRead.model_validate(item) for item in order.items],
        request_id=order.request_id,
        occurred_at=datetime.now(UTC),
    )
    await bus.publish(TOPIC_ORDER_CREATED, event.model_dump(mode="json"))


async def list_orders(session: AsyncSession, *, offset: int = 0, limit: int = 50) -> list[Order]:
    result = await session.scalars(select(Order).order_by(Order.id).offset(offset).limit(limit))
    return list(result)


async def get_order(session: AsyncSession, order_id: int) -> Order:
    order = await session.get(Order, order_id)
    if order is None:
        raise NotFoundError("Order not found")
    return order
