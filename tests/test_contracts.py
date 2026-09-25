from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from shared.contracts import TOPIC_ORDER_CREATED, ErrorEnvelope, OrderCreated


def _valid_event_payload() -> dict[str, object]:
    return {
        "event_id": str(uuid4()),
        "event_type": "order.created",
        "order_id": 1,
        "customer": "Alex",
        "degraded": False,
        "total": "1500.00",
        "items": [{"product_id": 1, "name": "Lamp", "quantity": 1, "unit_price": "1500.00"}],
        "request_id": "req-1",
        "occurred_at": datetime.now(UTC).isoformat(),
    }


def test_order_created_contract_accepts_valid_payload() -> None:
    event = OrderCreated.model_validate(_valid_event_payload())
    assert event.event_type == TOPIC_ORDER_CREATED
    assert event.total == Decimal("1500.00")


def test_order_created_contract_rejects_missing_fields() -> None:
    payload = _valid_event_payload()
    del payload["order_id"]
    with pytest.raises(ValidationError):
        OrderCreated.model_validate(payload)


def test_order_created_contract_rejects_wrong_event_type() -> None:
    payload = _valid_event_payload()
    payload["event_type"] = "order.cancelled"
    with pytest.raises(ValidationError):
        OrderCreated.model_validate(payload)


def test_error_envelope_shape() -> None:
    envelope = ErrorEnvelope(error={"code": "not_found", "message": "x", "request_id": "r"})
    dumped = envelope.model_dump(mode="json")
    assert set(dumped["error"]) == {"code", "message", "request_id"}


async def test_all_services_health(env) -> None:
    expected = {
        env.catalog_app: "catalog-service",
        env.order_app: "order-service",
        env.notification_app: "notification-service",
        env.gateway_app: "gateway",
    }
    for app, service_name in expected.items():
        client = env.client_for(app)
        async with client:
            resp = await client.get("/health")
        assert resp.status_code == 200, service_name
        assert resp.json()["service"] == service_name
