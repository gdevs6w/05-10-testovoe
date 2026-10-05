import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from faststream import FastStream
from faststream.rabbit import RabbitMessage

from app.consumer.processing import ProcessingError, emulate_processing
from app.db.session import async_session_factory
from app.models import PaymentStatus
from app.rabbit.broker import broker
from app.rabbit.topology import (
    PAYMENTS_DLX,
    PAYMENTS_DLQ_ROUTING_KEY,
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    PAYMENTS_RETRY_EXCHANGE,
    declare_topology,
)
from app.repositories.payment import PaymentRepository
from app.services.webhook import send_webhook

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
app = FastStream(broker)


@app.after_startup
async def _declare() -> None:
    await declare_topology(broker)


async def _schedule_retry(payload: dict, attempt: int) -> None:
    if attempt <= MAX_ATTEMPTS:
        await broker.publish(
            payload,
            exchange=PAYMENTS_RETRY_EXCHANGE,
            routing_key=f"payments.retry.{attempt}",
            headers={"x-retry-count": attempt},
        )
    else:
        await broker.publish(
            payload,
            exchange=PAYMENTS_DLX,
            routing_key=PAYMENTS_DLQ_ROUTING_KEY,
            headers={"x-retry-count": attempt},
        )


@broker.subscriber(PAYMENTS_NEW_QUEUE, PAYMENTS_EXCHANGE)
async def handle(payload: dict, msg: RabbitMessage) -> None:
    payment_id = UUID(payload["payment_id"])
    attempts = int(msg.headers.get("x-retry-count", 0))

    async with async_session_factory() as session:
        repo = PaymentRepository(session)
        payment = await repo.get_by_id(payment_id)

        if payment is None:
            logger.warning("payment %s not found, skip", payment_id)
            return
        if payment.status != PaymentStatus.PENDING:
            logger.info("payment %s already %s, skip", payment_id, payment.status)
            return

        try:
            await emulate_processing()
        except ProcessingError:
            logger.warning("payment %s processing failed (attempt %s)", payment_id, attempts + 1)
            await _schedule_retry(payload, attempts + 1)
            return

        payment.status = PaymentStatus.SUCCEEDED
        payment.processed_at = datetime.now(timezone.utc)
        await session.commit()
        webhook_url = payment.webhook_url
        status = payment.status.value
        processed_at = payment.processed_at.isoformat()

    logger.info("payment %s -> %s", payment_id, status)
    await send_webhook(
        webhook_url,
        {"payment_id": str(payment_id), "status": status, "processed_at": processed_at},
    )


if __name__ == "__main__":
    asyncio.run(app.run())