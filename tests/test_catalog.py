import httpx

from tests.conftest import PRODUCT, create_product


async def test_health(catalog_client: httpx.AsyncClient) -> None:
    resp = await catalog_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "catalog-service"}


async def test_product_crud(catalog_client: httpx.AsyncClient) -> None:
    product = await create_product(catalog_client)
    product_id = product["id"]

    listed = await catalog_client.get("/api/v1/products")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    got = await catalog_client.get(f"/api/v1/products/{product_id}")
    assert got.status_code == 200
    assert got.json()["sku"] == "SKU-1"

    updated = await catalog_client.put(f"/api/v1/products/{product_id}", json={"price": 1999.0})
    assert updated.status_code == 200
    assert float(updated.json()["price"]) == 1999.0

    deleted = await catalog_client.delete(f"/api/v1/products/{product_id}")
    assert deleted.status_code == 204
    assert (await catalog_client.get(f"/api/v1/products/{product_id}")).status_code == 404


async def test_duplicate_sku_rejected(catalog_client: httpx.AsyncClient) -> None:
    await create_product(catalog_client)
    dup = await catalog_client.post("/api/v1/products", json=PRODUCT)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "conflict"


async def test_not_found_has_request_id_envelope(catalog_client: httpx.AsyncClient) -> None:
    resp = await catalog_client.get("/api/v1/products/999", headers={"X-Request-ID": "req-abc"})
    assert resp.status_code == 404
    body = resp.json()["error"]
    assert body["code"] == "not_found"
    assert body["request_id"] == "req-abc"
    assert resp.headers["X-Request-ID"] == "req-abc"
