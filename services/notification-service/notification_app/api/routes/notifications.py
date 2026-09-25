"""Маршруты уведомлений: /api/v1/notifications."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from notification_app.core.database import get_session
from notification_app.models import Notification
from notification_app.services import notifications as notifications_service
from shared.contracts import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    order_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[Notification]:
    return await notifications_service.list_by_order(
        session, order_id=order_id, offset=offset, limit=limit
    )


@router.get("/{notification_id}", response_model=NotificationRead)
async def get_notification(
    notification_id: int, session: AsyncSession = Depends(get_session)
) -> Notification:
    return await notifications_service.get_notification(session, notification_id)
