import uuid
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import ApiKey, DbSession
from app.models import Payment
from app.repositories.payment import PaymentRepository
from app.schemas.payment import PaymentAccepted, PaymentCreate, PaymentResponse

router = APIRouter(tags=["payments"])


def _build_event(payment: Payment) -> dict:
    return {
        "payment_id": str(payment.id),
        "amount": str(payment.amount),
        "currency": payment.currency.value,
        "webhook_url": payment.webhook_url,
    }


@router.post(
    "/payments",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PaymentAccepted,
)
async def create_payment(
    payload: PaymentCreate,
    session: DbSession,
    _: ApiKey,
    idempotency_key: str = Header(...),
) -> PaymentAccepted:
    repo = PaymentRepository(session)

    existing = await repo.get_by_idempotency_key(idempotency_key)
    if existing is not None:
        return PaymentAccepted(
            payment_id=existing.id,
            status=existing.status,
            created_at=existing.created_at,
        )

    payment = Payment(
        id=uuid.uuid4(),
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        meta=payload.metadata or {},
        idempotency_key=idempotency_key,
        webhook_url=str(payload.webhook_url),
    )

    try:
        await repo.create_with_outbox(payment, _build_event(payment))
    except IntegrityError:
        await session.rollback()
        existing = await repo.get_by_idempotency_key(idempotency_key)
        if existing is None:
            raise
        return PaymentAccepted(
            payment_id=existing.id,
            status=existing.status,
            created_at=existing.created_at,
        )

    return PaymentAccepted(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: UUID, session: DbSession, _: ApiKey) -> Payment:
    repo = PaymentRepository(session)
    payment = await repo.get_by_id(payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    return payment
