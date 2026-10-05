from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Outbox, Payment


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def create_with_outbox(
        self, payment: Payment, event_payload: dict
    ) -> Payment:
        self.session.add(payment)
        await self.session.flush()
        self.session.add(
            Outbox(
                event_type="payment.created",
                aggregate_id=payment.id,
                payload=event_payload,
            )
        )
        await self.session.commit()
        return payment
