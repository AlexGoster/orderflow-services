from fastapi import APIRouter

from order_app.api.routes import orders

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(orders.router)
