FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/services/gateway:/app/services/order-service:/app/services/catalog-service:/app/services/notification-service

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY shared ./shared
COPY services ./services

USER app

ARG SERVICE=gateway
ENV SERVICE=${SERVICE}
EXPOSE 8000
CMD ["python", "-m", "shared.launch"]
