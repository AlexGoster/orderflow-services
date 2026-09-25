"""Единая точка входа шлюза: маршрутизация /api/v1/* по сервисам."""

from fastapi import APIRouter, Depends, Request, Response

from gateway_app.core.clients import CATALOG, NOTIFICATION, ORDER, ServiceClients
from gateway_app.core.proxy import proxy_request
from shared.contracts import NotificationRead, OrderRead, ProductRead

router = APIRouter(tags=["gateway"])


def get_clients(request: Request) -> ServiceClients:
    clients: ServiceClients = request.app.state.clients
    return clients


# --- catalog-service -------------------------------------------------------


@router.get("/products", response_model=list[ProductRead])
async def list_products(
    request: Request, clients: ServiceClients = Depends(get_clients)
) -> Response:
    return await proxy_request(clients.get(CATALOG), request, service="catalog-service")


@router.post("/products", response_model=ProductRead, status_code=201)
async def create_product(
    request: Request, clients: ServiceClients = Depends(get_clients)
) -> Response:
    return await proxy_request(clients.get(CATALOG), request, service="catalog-service")


@router.get("/products/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int, request: Request, clients: ServiceClients = Depends(get_clients)
) -> Response:
    return await proxy_request(clients.get(CATALOG), request, service="catalog-service")


@router.put("/products/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int, request: Request, clients: ServiceClients = Depends(get_clients)
) -> Response:
    return await proxy_request(clients.get(CATALOG), request, service="catalog-service")


@router.delete("/products/{product_id}", status_code=204)
async def delete_product(
    product_id: int, request: Request, clients: ServiceClients = Depends(get_clients)
) -> Response:
    return await proxy_request(clients.get(CATALOG), request, service="catalog-service")


# --- order-service ---------------------------------------------------------


@router.post("/orders", response_model=OrderRead, status_code=201)
async def create_order(
    request: Request, clients: ServiceClients = Depends(get_clients)
) -> Response:
    return await proxy_request(clients.get(ORDER), request, service="order-service")


@router.get("/orders", response_model=list[OrderRead])
async def list_orders(request: Request, clients: ServiceClients = Depends(get_clients)) -> Response:
    return await proxy_request(clients.get(ORDER), request, service="order-service")


@router.get("/orders/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: int, request: Request, clients: ServiceClients = Depends(get_clients)
) -> Response:
    return await proxy_request(clients.get(ORDER), request, service="order-service")


# --- notification-service --------------------------------------------------


@router.get("/notifications", response_model=list[NotificationRead])
async def list_notifications(
    request: Request, clients: ServiceClients = Depends(get_clients)
) -> Response:
    return await proxy_request(clients.get(NOTIFICATION), request, service="notification-service")
