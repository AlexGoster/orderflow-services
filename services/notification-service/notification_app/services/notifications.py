"""«Отправка» уведомлений: запись в свою БД + структурированный лог."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from notification_app.models import Notification
from shared.contracts import OrderCreated
from shared.errors import NotFoundError

logger = logging.getLogger(__name__)


async def send_order_notification(
    session: AsyncSession, event: OrderCreated
) -> Notification | None:
    """Идемпотентно: на один заказ создаётся ровно одно уведомление."""
    existing = await session.scalar(
        select(Notification).where(Notification.order_id == event.order_id)
    )
    if existing is not None:
        return existing

    body_lines = [
        f"Клиент: {event.customer}",
        f"Сумма: {event.total}",
        f"Позиций: {len(event.items)}",
    ]
    if event.degraded:
        body_lines.append("Принято без проверки каталога (режим degraded)")

    notification = Notification(
        order_id=event.order_id,
        channel="email",
        subject=f"Заказ #{event.order_id} создан",
        body="\n".join(body_lines),
        request_id=event.request_id,
    )
    session.add(notification)
    await session.commit()
    await session.refresh(notification)
    logger.info(
        "notification sent",
        extra={
            "order_id": event.order_id,
            "channel": "email",
            "notification_id": notification.id,
        },
    )
    return notification


async def list_by_order(
    session: AsyncSession, *, order_id: int, offset: int = 0, limit: int = 50
) -> list[Notification]:
    result = await session.scalars(
        select(Notification)
        .where(Notification.order_id == order_id)
        .order_by(Notification.id)
        .offset(offset)
        .limit(limit)
    )
    return list(result)


async def get_notification(session: AsyncSession, notification_id: int) -> Notification:
    notification = await session.get(Notification, notification_id)
    if notification is None:
        raise NotFoundError("Notification not found")
    return notification
