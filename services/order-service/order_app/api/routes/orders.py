"""Маршруты заказов: /api/v1/orders."""

import logging

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from order_app.core.catalog_client import CatalogClient
from order_app.core.database import get_session
from order_app.models import Order
from order_app.services import orders as orders_service
from shared.context import get_request_id
from shared.contracts import OrderCreate, OrderRead
from shared.events import EventBus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


def get_catalog_client(request: Request) -> CatalogClient:
    client: CatalogClient = request.app.state.catalog_client
    return client


def get_event_bus(request: Request) -> EventBus:
    bus: EventBus = request.app.state.bus
    return bus


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_session),
    catalog: CatalogClient = Depends(get_catalog_client),
    bus: EventBus = Depends(get_event_bus),
) -> Order:
    order = await orders_service.create_order(
        session, payload=payload, catalog=catalog, request_id=get_request_id()
    )
    try:
        await orders_service.publish_order_created(bus, order)
    except Exception as exc:  # публикация не должна ломать ответ клиенту
        logger.warning(
            "failed to publish order.created",
            extra={"order_id": order.id, "error": str(exc)},
        )
    return order


@router.get("", response_model=list[OrderRead])
async def list_orders(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[Order]:
    return await orders_service.list_orders(session, offset=offset, limit=limit)


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: int, session: AsyncSession = Depends(get_session)) -> Order:
    return await orders_service.get_order(session, order_id)
