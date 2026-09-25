import httpx

from tests.conftest import create_product


async def test_gateway_routes_to_catalog(gateway: httpx.AsyncClient) -> None:
    product = await create_product(gateway)
    assert product["sku"] == "SKU-1"

    listed = await gateway.get("/api/v1/products")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    got = await gateway.get(f"/api/v1/products/{product['id']}")
    assert got.status_code == 200

    updated = await gateway.put(f"/api/v1/products/{product['id']}", json={"stock": 42})
    assert updated.json()["stock"] == 42

    assert (await gateway.delete(f"/api/v1/products/{product['id']}")).status_code == 204


async def test_end_to_end_order_flow_creates_notification(gateway: httpx.AsyncClient) -> None:
    product = await create_product(gateway)

    created = await gateway.post(
        "/api/v1/orders",
        json={"customer": "Alex", "items": [{"product_id": product["id"], "quantity": 2}]},
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["id"]
    assert created.json()["degraded"] is False

    notifications = await gateway.get("/api/v1/notifications", params={"order_id": order_id})
    assert notifications.status_code == 200
    assert len(notifications.json()) == 1

    orders = await gateway.get("/api/v1/orders")
    assert len(orders.json()) == 1
    assert (await gateway.get(f"/api/v1/orders/{order_id}")).status_code == 200


async def test_gateway_propagates_correlation_id(gateway: httpx.AsyncClient) -> None:
    product = await create_product(gateway)
    created = await gateway.post(
        "/api/v1/orders",
        headers={"X-Request-ID": "gw-trace-1"},
        json={"customer": "Alex", "items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert created.headers["X-Request-ID"] == "gw-trace-1"
    assert created.json()["request_id"] == "gw-trace-1"


async def test_gateway_returns_503_when_order_service_down(env) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    app = env.gateway_app
    app.state.clients._clients["order"] = httpx.AsyncClient(  # noqa: SLF001
        base_url="http://order-down",
        transport=httpx.MockTransport(boom),
    )
    client = env.client_for(app, "http://gateway")
    async with client:
        resp = await client.post(
            "/api/v1/orders", json={"customer": "Alex", "items": [{"product_id": 1, "quantity": 1}]}
        )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "service_unavailable"


async def test_gateway_health(gateway: httpx.AsyncClient) -> None:
    resp = await gateway.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "gateway"
