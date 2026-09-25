"""HTTP-клиенты шлюза: по одному на каждый downstream-сервис."""

from collections.abc import Mapping

import httpx

from gateway_app.core.config import Settings

CATALOG = "catalog"
ORDER = "order"
NOTIFICATION = "notification"


class ServiceClients:
    """Пул клиентов httpx; в тестах вместо сети подставляется ASGITransport."""

    def __init__(
        self,
        settings: Settings,
        *,
        transports: Mapping[str, httpx.AsyncBaseTransport] | None = None,
    ) -> None:
        routes = dict(transports or {})
        self._clients: dict[str, httpx.AsyncClient] = {
            CATALOG: httpx.AsyncClient(
                base_url=settings.catalog_service_url,
                transport=routes.get(CATALOG),
                timeout=settings.timeout,
            ),
            ORDER: httpx.AsyncClient(
                base_url=settings.order_service_url,
                transport=routes.get(ORDER),
                timeout=settings.timeout,
            ),
            NOTIFICATION: httpx.AsyncClient(
                base_url=settings.notification_service_url,
                transport=routes.get(NOTIFICATION),
                timeout=settings.timeout,
            ),
        }

    def get(self, service: str) -> httpx.AsyncClient:
        return self._clients[service]

    async def aclose(self) -> None:
        for client in self._clients.values():
            await client.aclose()
