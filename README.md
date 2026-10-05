# Payments

Сервис асинхронной обработки платежей. Принимает запрос, пишет платёж и событие
в outbox одной транзакцией, фоновым воркером публикует событие в RabbitMQ, а
consumer эмулирует обработку шлюза и уведомляет клиента через webhook.

Стек: FastAPI + Pydantic v2, SQLAlchemy 2.0 (async) + asyncpg, PostgreSQL,
RabbitMQ (FastStream), Alembic, Docker.

## Запуск

    docker compose up --build

Поднимутся postgres, rabbitmq, api и consumer. Миграции api применяет сам при
старте.

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- RabbitMQ UI: http://localhost:15672 (guest/guest)

## API

Все запросы требуют заголовок `X-API-Key` (по умолчанию `change-me`).

Создание платежа (`Idempotency-Key` обязателен, повтор с тем же ключом вернёт
тот же платёж):

    curl -X POST http://localhost:8000/api/v1/payments \
      -H "X-API-Key: change-me" \
      -H "Idempotency-Key: order-123" \
      -H "Content-Type: application/json" \
      -d '{"amount":"100.00","currency":"RUB","description":"Оплата заказа","metadata":{"order_id":"123"},"webhook_url":"https://example.com/hook"}'

Ответ `202 Accepted`:

    {"payment_id":"...","status":"pending","created_at":"..."}

Получение платежа:

    curl http://localhost:8000/api/v1/payments/<payment_id> \
      -H "X-API-Key: change-me"

## Как это работает

1. `POST /payments` в одной транзакции создаёт платёж и запись в `outbox`.
2. Фоновая задача в api читает `outbox` и публикует событие в exchange
   `payments` (очередь `payments.new`).
3. Consumer берёт событие, эмулирует обработку 2–5 c (90% успех), обновляет
   статус и шлёт webhook (3 попытки с задержкой).
4. При ошибке обработки сообщение повторяется до 3 попыток (паузы 2 и 4 c
   через `payments.retry.1/2`), затем платёж помечается `failed` и уходит в
   `payments.dlq`. Результат (`succeeded`/`failed`) отправляется на webhook.
5. Непойманные исключения consumer'а тоже попадают в `payments.dlq`: у очереди
   `payments.new` настроен dead-letter exchange.

## Конфиг

Через переменные окружения (полный список - в `.env.example`): `API_KEY`,
`DATABASE_URL`, `RABBITMQ_URL`, `OUTBOX_POLL_INTERVAL`, `PROCESSING_SUCCESS_RATE` и др.

## Тесты

    venv\Scripts\python -m pytest

Проверяется создание платежа, идемпотентность, запись события в outbox,
отсутствие ключа (401) и получение платежа.
