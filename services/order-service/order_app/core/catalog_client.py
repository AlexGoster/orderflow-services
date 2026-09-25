"""Клиент catalog-service: retry (tenacity) + circuit breaker + фолбэк degraded."""

import logging

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from order_app.core.resilience import CircuitBreaker, CircuitOpenError
from shared.context import get_request_id
from shared.contracts import ProductRead
from shared.errors import NotFoundError

logger = logging.getLogger(__name__)


class CatalogError(Exception):
    """Базовая ошибка обращения к catalog-service."""


class CatalogUnavailableError(CatalogError):
    """Сервис недоступен или контур разомкнут — заказ уйдёт в degraded."""


def _is_retryable(exception: BaseException) -> bool:
    if isinstance(exception, httpx.TransportError):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code >= 500
    return False


class CatalogClient:
    """GET /api/v1/products/{id} с повторами и автоматическим размыканием контура."""

    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        breaker: CircuitBreaker | None = None,
        timeout: float = 3.0,
        max_attempts: int = 3,
        wait_multiplier: float = 0.05,
        wait_max: float = 0.5,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, transport=transport, timeout=timeout)
        self.breaker = breaker or CircuitBreaker()
        self._max_attempts = max_attempts
        self._wait_multiplier = wait_multiplier
        self._wait_max = wait_max

    async def get_product(self, product_id: int) -> ProductRead:
        try:
            self.breaker.before_call()
        except CircuitOpenError as exc:
            logger.warning("catalog circuit is open", extra={"product_id": product_id})
            raise CatalogUnavailableError(f"circuit open for product {product_id}") from exc

        try:
            product = await self._get_with_retry(product_id)
        except NotFoundError:
            self.breaker.record_success()
            raise
        except CatalogUnavailableError:
            self.breaker.record_failure()
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                self.breaker.record_failure()
            raise CatalogUnavailableError(
                f"catalog-service answered {exc.response.status_code}"
            ) from exc
        except httpx.TransportError as exc:
            self.breaker.record_failure()
            raise CatalogUnavailableError(f"catalog-service unreachable: {exc}") from exc

        self.breaker.record_success()
        return product

    async def _get_with_retry(self, product_id: int) -> ProductRead:
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=self._wait_multiplier, max=self._wait_max),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                return await self._request_product(product_id)
        # tenacity выходит из цикла только возвратом или исключением
        raise CatalogUnavailableError("retries exhausted")  # pragma: no cover

    async def _request_product(self, product_id: int) -> ProductRead:
        headers: dict[str, str] = {}
        request_id = get_request_id()
        if request_id:
            headers["X-Request-ID"] = request_id
        response = await self._client.get(f"/api/v1/products/{product_id}", headers=headers)
        if response.status_code == 404:
            raise NotFoundError(f"Product {product_id} not found")
        response.raise_for_status()
        return ProductRead.model_validate(response.json())

    async def aclose(self) -> None:
        await self._client.aclose()
