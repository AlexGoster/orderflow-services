# Проверка проекта

Проверки выполнялись 10–20 октября 2026. Исходная рабочая копия была чистой.

27 тестов прошли. ASGI: 4 сервиса, retry/circuit breaker/degraded, correlation ID, идемпотентность уведомлений; Ruff/strict mypy. Docker image собран.

API без аутентификации, резервирования склада или платежей. Redis pub/sub не гарантирует доставку при отключённом подписчике. create_all создаёт новую схему, но не заменяет миграции существующей.

## Повторный запуск

Команды из папки проекта после создания и активации Python venv. Для API задайте DATABASE_URL отдельной локальной БД и тестовый SECRET_KEY по примеру конфигурации; не используйте рабочие подключения.

```bash
python -m venv .venv
# Активируйте .venv согласно ОС.
python -m pip install -r requirements.txt -r requirements-dev.txt
# Полный локальный стек:
docker compose -p orderflow-services-local up --build -d
```

Тесты в отдельном тестовом окружении:

```bash
python -m pytest -o addopts= -q
```

Docker-проверки использовали отдельную сеть, PostgreSQL *_test и Redis; реальные данные, платежи и внешние сообщения не затрагивались. Результат локального запуска не означает production-ready.

20 октября прошла цепочка четырёх настоящих HTTP-контейнеров: товар → заказ → Redis → уведомление в PostgreSQL; 404/422 и correlation ID подтверждены.
