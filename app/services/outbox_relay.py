import asyncio

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.rabbit.broker import broker
from app.rabbit.topology import (
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_QUEUE,
    PAYMENTS_NEW_ROUTING_KEY,
)
from app.repositories.outbox import OutboxRepository

settings = get_settings()


async def _publish_batch() -> None:
    async with async_session_factory() as session:
        async with session.begin():
            repo = OutboxRepository(session)
            for event in await repo.fetch_pending(settings.outbox_batch_size):
                await broker.publish(
                    event.payload,
                    exchange=PAYMENTS_EXCHANGE,
                    routing_key=PAYMENTS_NEW_ROUTING_KEY,
                )
                await repo.mark_published(event)


async def run_outbox_relay() -> None:
    async with broker:
        exchange = await broker.declare_exchange(PAYMENTS_EXCHANGE)
        queue = await broker.declare_queue(PAYMENTS_NEW_QUEUE)
        await queue.bind(exchange, routing_key=PAYMENTS_NEW_ROUTING_KEY)
        while True:
            await _publish_batch()
            await asyncio.sleep(settings.outbox_poll_interval)