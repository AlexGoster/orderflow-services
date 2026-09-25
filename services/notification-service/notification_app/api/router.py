from fastapi import APIRouter

from notification_app.api.routes import notifications

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(notifications.router)
