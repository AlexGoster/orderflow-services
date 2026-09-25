from fastapi import APIRouter

from catalog_app.api.routes import products

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(products.router)
