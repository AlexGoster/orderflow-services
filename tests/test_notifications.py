import httpx

from tests.conftest import create_product


async def test_order_created_produces_single_notification(
    env, catalog_client: httpx.AsyncClient, order_client: httpx.AsyncClient
) -> None:
    product = await create_product(catalog_client)
    created = await order_client.post(
        "/api/v1/orders",
        json={"customer": "Alex", "items": [{"product_id": product["id"], "quantity": 3}]},
    )
    order_id = created.json()["id"]

    client = env.client_for(env.notification_app, "http://notification")
    async with client:
        resp = await client.get("/api/v1/notifications", params={"order_id": order_id})
    assert resp.status_code == 200
    notifications = resp.json()
    assert len(notifications) == 1
    assert notifications[0]["channel"] == "email"
    assert notifications[0]["order_id"] == order_id


async def test_duplicate_event_is_idempotent(env) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal
    from uuid import uuid4

    from shared.contracts import TOPIC_ORDER_CREATED, OrderCreated

    event = OrderCreated(
        event_id=uuid4(),
        order_id=777,
        customer="Alex",
        degraded=False,
        total=Decimal("100"),
        items=[],
        request_id="req-1",
        occurred_at=datetime.now(UTC),
    )
    payload = event.model_dump(mode="json")

    await env.bus.publish(TOPIC_ORDER_CREATED, payload)
    await env.bus.publish(TOPIC_ORDER_CREATED, payload)

    client = env.client_for(env.notification_app, "http://notification")
    async with client:
        resp = await client.get("/api/v1/notifications", params={"order_id": 777})
    assert len(resp.json()) == 1


async def test_notification_endpoints(env) -> None:
    from datetime import UTC, datetime
    from decimal import Decimal
    from uuid import uuid4

    from shared.contracts import TOPIC_ORDER_CREATED, OrderCreated

    event = OrderCreated(
        event_id=uuid4(),
        order_id=42,
        customer="Sam",
        degraded=True,
        total=Decimal("10"),
        items=[],
        request_id="req-2",
        occurred_at=datetime.now(UTC),
    )
    await env.bus.publish(TOPIC_ORDER_CREATED, event.model_dump(mode="json"))

    client = env.client_for(env.notification_app, "http://notification")
    async with client:
        listed = await client.get("/api/v1/notifications", params={"order_id": 42})
        notification_id = listed.json()[0]["id"]
        got = await client.get(f"/api/v1/notifications/{notification_id}")
        missing = await client.get("/api/v1/notifications/9999")

    assert got.status_code == 200
    assert "42" in got.json()["subject"]
    assert missing.status_code == 404
