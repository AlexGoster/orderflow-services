"""Общие Pydantic-контракты: API-схемы и события шины.

Всё, что передаётся между сервисами (HTTP-тела, события), объявлено здесь.
Сервисные ORM-модели остаются локальными и в контрактах не участвуют.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Топики шины событий
TOPIC_ORDER_CREATED = "order.created"


class ErrorBody(BaseModel):
    """Тело ошибки в едином формате всех сервисов."""

    code: str
    message: str
    request_id: str = ""


class ErrorEnvelope(BaseModel):
    """Обёрочка ошибки: {"error": {...}}."""

    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    stock: int | None = Field(default=None, ge=0)


class ProductRead(ProductCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


class OrderItemIn(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(gt=0, le=1000)


class OrderCreate(BaseModel):
    customer: str = Field(min_length=1, max_length=255)
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    name: str
    quantity: int
    unit_price: Decimal


class OrderStatus(StrEnum):
    created = "created"
    shipped = "shipped"
    cancelled = "cancelled"


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer: str
    status: OrderStatus
    degraded: bool
    warnings: list[str]
    total: Decimal
    items: list[OrderItemRead]
    request_id: str
    created_at: datetime


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    channel: str
    subject: str
    body: str
    request_id: str
    created_at: datetime


class OrderCreated(BaseModel):
    """Событие order.created — публикуется order-service в шину."""

    event_id: UUID
    event_type: Literal["order.created"] = "order.created"
    order_id: int
    customer: str
    degraded: bool
    total: Decimal
    items: list[OrderItemRead]
    request_id: str
    occurred_at: datetime
