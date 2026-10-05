import asyncio
import logging

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.rabbit.broker import broker
from app.rabbit.topology import (
    PAYMENTS_EXCHANGE,
    PAYMENTS_NEW_ROUTING_KEY,
    declare_topology,
)
from app.repositories.outbox import OutboxRepository

logger = logging.getLogger(__name__)
settings = get_settings()


async def _publish_batch() -> None:
    async with async_session_factory() as session, session.begin():
        repo = OutboxRepository(session)
        for event in await repo.fetch_pending(settings.outbox_batch_size):
            await broker.publish(
                event.payload,
                exchange=PAYMENTS_EXCHANGE,
                routing_key=PAYMENTS_NEW_ROUTING_KEY,
            )
            await repo.mark_published(event)


async def run_outbox_relay() -> None:
    while True:
        try:
            async with broker:
                await declare_topology(broker)
                while True:
                    await _publish_batch()
                    await asyncio.sleep(settings.outbox_poll_interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "outbox relay connection error, retry in %ss",
                settings.outbox_poll_interval,
            )
            await asyncio.sleep(settings.outbox_poll_interval)
