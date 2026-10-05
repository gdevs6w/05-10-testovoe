import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from faststream import FastStream
from faststream.rabbit import RabbitMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.consumer.processing import ProcessingError, emulate_processing
from app.db.session import async_session_factory
from app.models import Payment, PaymentStatus
from app.rabbit.broker import broker
from app.rabbit.topology import (
    PAYMENTS_DLQ_ROUTING_KEY,
    PAYMENTS_DLX,
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    PAYMENTS_RETRY_EXCHANGE,
    declare_topology,
)
from app.repositories.payment import PaymentRepository
from app.services.webhook import send_webhook

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

MAX_ATTEMPTS = 3
app = FastStream(broker)


@app.after_startup
async def _declare() -> None:
    await declare_topology(broker)


async def _retry_later(payload: dict, attempt: int) -> None:
    await broker.publish(
        payload,
        exchange=PAYMENTS_RETRY_EXCHANGE,
        routing_key=f"payments.retry.{attempt}",
        headers={"x-retry-count": attempt},
    )


async def _send_to_dlq(payload: dict, attempt: int) -> None:
    await broker.publish(
        payload,
        exchange=PAYMENTS_DLX,
        routing_key=PAYMENTS_DLQ_ROUTING_KEY,
        headers={"x-retry-count": attempt},
    )


def _webhook_payload(payment: Payment) -> dict:
    return {
        "payment_id": str(payment.id),
        "status": payment.status.value,
        "processed_at": payment.processed_at.isoformat()
        if payment.processed_at
        else None,
    }


async def _handle_failure(
    session: AsyncSession,
    payment: Payment,
    payload: dict,
    attempts: int,
) -> None:
    next_attempt = attempts + 1

    if next_attempt < MAX_ATTEMPTS:
        logger.warning(
            "payment %s failed, retry %s/%s",
            payment.id,
            next_attempt,
            MAX_ATTEMPTS - 1,
        )
        await _retry_later(payload, next_attempt)
        return

    payment.status = PaymentStatus.FAILED
    payment.processed_at = datetime.now(timezone.utc)
    await session.commit()
    logger.warning(
        "payment %s failed after %s attempts -> DLQ", payment.id, next_attempt
    )

    await send_webhook(payment.webhook_url, _webhook_payload(payment))
    await _send_to_dlq(payload, next_attempt)


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
            await _handle_failure(session, payment, payload, attempts)
            return

        payment.status = PaymentStatus.SUCCEEDED
        payment.processed_at = datetime.now(timezone.utc)
        await session.commit()
        webhook_url = payment.webhook_url
        webhook_payload = _webhook_payload(payment)

    logger.info("payment %s -> succeeded", payment_id)
    await send_webhook(webhook_url, webhook_payload)


if __name__ == "__main__":
    asyncio.run(app.run())
