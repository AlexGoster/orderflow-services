from fastapi import APIRouter

from gateway_app.api.routes import proxy

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(proxy.router)
