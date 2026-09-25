"""Структурированное (JSON) логирование с correlation id."""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from shared.context import get_request_id

_RESERVED_FIELDS = frozenset(
    logging.LogRecord(
        name="", level=logging.INFO, pathname="", lineno=0, msg="", args=(), exc_info=None
    ).__dict__.keys()
) | frozenset({"message", "asctime", "request_id"})


class RequestIdFilter(logging.Filter):
    """Подставляет в каждую запись текущий request_id, если он не задан явно."""

    def filter(self, record: logging.LogRecord) -> bool:
        if "request_id" not in record.__dict__:
            record.__dict__["request_id"] = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Одна строка JSON на событие: ts, level, service, logger, request_id + extras."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": self._service,
            "logger": record.name,
            "request_id": record.__dict__.get("request_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(service: str, module_name: str) -> logging.Logger:
    """Идемпотентно настраивает JSON-хендлер на корневом логгере пакета сервиса.

    ``module_name`` — ``__name__`` из ``<service_pkg>/main.py``; обработчик
    вешается на сам пакет, поэтому ``logging.getLogger(__name__)`` во всех
    модулях сервиса попадает в одну структурированную строку лога.
    """
    root = logging.getLogger(module_name.split(".")[0])
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter(service))
        handler.addFilter(RequestIdFilter())
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        root.propagate = False
    return root
