"""Launch the service selected by the Docker build argument."""

import os

import uvicorn

TARGETS = {
    "gateway": ("gateway_app.main:create_app", 8000),
    "catalog-service": ("catalog_app.main:create_app", 8001),
    "order-service": ("order_app.main:create_app", 8002),
    "notification-service": ("notification_app.main:create_app", 8003),
}


def main() -> None:
    service = os.environ.get("SERVICE", "gateway")
    if service not in TARGETS:
        raise SystemExit(f"Unknown service: {service}")
    target, port = TARGETS[service]
    uvicorn.run(target, factory=True, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
