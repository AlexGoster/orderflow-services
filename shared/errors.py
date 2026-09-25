"""Единый формат ошибок и обработчики исключений для всех сервисов."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.context import get_request_id
from shared.contracts import ErrorBody, ErrorEnvelope


class AppError(Exception):
    def __init__(self, message: str, code: str = "app_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, code="not_found", status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message, code="conflict", status_code=409)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str = "Upstream service is unavailable") -> None:
        super().__init__(message, code="service_unavailable", status_code=503)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        envelope = ErrorEnvelope(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                request_id=get_request_id(),
            )
        )
        return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(mode="json"))
