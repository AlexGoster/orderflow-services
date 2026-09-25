import time

import httpx
import pytest

from order_app.core.catalog_client import CatalogClient, CatalogUnavailableError
from order_app.core.resilience import CircuitBreaker, CircuitOpenError, CircuitState
from shared.errors import NotFoundError


def _failing_transport(calls: list[int]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectError("connection refused", request=request)

    return httpx.MockTransport(handler)


async def test_retry_recovers_after_transient_failures() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectError("temporary glitch", request=request)
        return httpx.Response(200, json={"id": 1, "sku": "S", "name": "N", "price": 10, "stock": 1})

    client = CatalogClient(
        "http://catalog",
        transport=httpx.MockTransport(handler),
        max_attempts=3,
        wait_multiplier=0.01,
    )
    product = await client.get_product(1)
    assert product.id == 1
    assert len(calls) == 3, "tenacity должен сделать ровно 3 попытки"
    await client.aclose()


async def test_circuit_opens_after_threshold_failures() -> None:
    calls: list[int] = []
    client = CatalogClient(
        "http://catalog",
        transport=_failing_transport(calls),
        breaker=CircuitBreaker(failure_threshold=2, recovery_timeout=60.0),
        max_attempts=1,
        wait_multiplier=0.01,
    )

    for _ in range(2):
        with pytest.raises(CatalogUnavailableError):
            await client.get_product(1)
    assert client.breaker.state is CircuitState.open

    attempts_before = len(calls)
    with pytest.raises(CatalogUnavailableError):
        await client.get_product(1)
    assert len(calls) == attempts_before, "открытый контур не должен ходить в сеть"
    await client.aclose()


async def test_not_found_does_not_trip_breaker() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"code": "not_found", "message": "no"}})

    client = CatalogClient(
        "http://catalog",
        transport=httpx.MockTransport(handler),
        breaker=CircuitBreaker(failure_threshold=1, recovery_timeout=60.0),
        max_attempts=1,
    )
    with pytest.raises(NotFoundError):
        await client.get_product(404)
    assert client.breaker.state is CircuitState.closed
    await client.aclose()


def test_breaker_transitions() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60.0)
    assert breaker.state is CircuitState.closed

    breaker.before_call()
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state is CircuitState.open
    with pytest.raises(CircuitOpenError):
        breaker.before_call()

    breaker._opened_at = time.monotonic() - 61  # имитируем истёкший recovery_timeout
    assert breaker.state is CircuitState.half_open, "после recovery_timeout — half_open"
    breaker.record_success()
    assert breaker.state is CircuitState.closed
    assert breaker.failures == 0
