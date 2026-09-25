import httpx

from tests.conftest import create_product


async def test_create_order_with_verified_prices(
    env, catalog_client: httpx.AsyncClient, order_client: httpx.AsyncClient
) -> None:
    product = await create_product(catalog_client)

    resp = await order_client.post(
        "/api/v1/orders",
        json={"customer": "Alex", "items": [{"product_id": product["id"], "quantity": 2}]},
    )
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["degraded"] is False
    assert float(order["total"]) == 3000
    assert order["items"][0]["name"] == "Desk Lamp"
    assert order["status"] == "created"


async def test_order_degraded_when_catalog_down(env) -> None:
    client = env.client_for(env.degraded_order_app, "http://order")
    async with client:
        resp = await client.post(
            "/api/v1/orders",
            json={"customer": "Alex", "items": [{"product_id": 1, "quantity": 1}]},
        )
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["degraded"] is True
    assert order["warnings"]
    assert "catalog-service unavailable" in order["warnings"][0]
    assert float(order["total"]) == 0


async def test_order_created_event_published_to_bus(
    env, catalog_client: httpx.AsyncClient, order_client: httpx.AsyncClient
) -> None:
    product = await create_product(catalog_client)
    await order_client.post(
        "/api/v1/orders",
        json={"customer": "Alex", "items": [{"product_id": product["id"], "quantity": 1}]},
    )
    topics = [topic for topic, _ in env.bus.published]
    assert "order.created" in topics


async def test_correlation_id_propagates_to_order(
    catalog_client: httpx.AsyncClient, order_client: httpx.AsyncClient
) -> None:
    product = await create_product(catalog_client)
    resp = await order_client.post(
        "/api/v1/orders",
        headers={"X-Request-ID": "trace-123"},
        json={"customer": "Alex", "items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert resp.headers["X-Request-ID"] == "trace-123"
    assert resp.json()["request_id"] == "trace-123"


async def test_list_and_get_order(
    catalog_client: httpx.AsyncClient, order_client: httpx.AsyncClient
) -> None:
    product = await create_product(catalog_client)
    created = await order_client.post(
        "/api/v1/orders",
        json={"customer": "Alex", "items": [{"product_id": product["id"], "quantity": 1}]},
    )
    order_id = created.json()["id"]

    listed = await order_client.get("/api/v1/orders")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    assert (await order_client.get(f"/api/v1/orders/{order_id}")).status_code == 200
    assert (await order_client.get("/api/v1/orders/999")).status_code == 404


async def test_order_validation_rejects_empty_items(order_client: httpx.AsyncClient) -> None:
    resp = await order_client.post("/api/v1/orders", json={"customer": "Alex", "items": []})
    assert resp.status_code == 422
