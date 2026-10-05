from datetime import datetime, timezone
from sqlalchemy import select
from collections.abc import Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Outbox, OutboxStatus


class OutboxRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def fetch_pending(self, limit: int) -> Sequence[Outbox]:
        result = await self.session.execute(
            select(Outbox)
            .where(Outbox.status == OutboxStatus.PENDING)
            .order_by(Outbox.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return result.scalars().all()


    async def mark_published(self, event: Outbox) -> None:
        event.status = OutboxStatus.PUBLISHED
        event.published_at = datetime.now(timezone.utc)
