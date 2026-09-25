"""Проксирование запросов шлюза в downstream-сервисы."""

import httpx
from fastapi import Request
from fastapi.responses import Response

from shared.context import get_request_id
from shared.errors import ServiceUnavailableError


async def proxy_request(client: httpx.AsyncClient, request: Request, *, service: str) -> Response:
    """Пересылает метод/путь/query/тело и обязательно — X-Request-ID."""
    body = await request.body()
    url = request.url.path
    if request.url.query:
        url = f"{url}?{request.url.query}"

    request_id = get_request_id()
    headers: dict[str, str] = {"X-Request-ID": request_id} if request_id else {}
    content_type = request.headers.get("content-type")
    if content_type:
        headers["Content-Type"] = content_type

    try:
        upstream = await client.request(request.method, url, content=body or None, headers=headers)
    except httpx.TimeoutException as exc:
        raise ServiceUnavailableError(f"{service} did not respond in time") from exc
    except httpx.TransportError as exc:
        raise ServiceUnavailableError(f"{service} is unavailable") from exc

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
