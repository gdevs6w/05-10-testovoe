from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl

from app.models import Currency, PaymentStatus


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: Currency
    description: str = Field(max_length=200)
    metadata: dict | None = Field(
        default=None, validation_alias=AliasChoices("meta", "metadata")
    )
    webhook_url: HttpUrl


class PaymentAccepted(BaseModel):
    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


class PaymentResponse(BaseModel):
    id: UUID
    amount: Decimal = Field(gt=0)
    currency: Currency
    description: str = Field(max_length=200)
    metadata: dict | None = Field(
        default=None, validation_alias=AliasChoices("meta", "metadata")
    )
    status: PaymentStatus
    webhook_url: HttpUrl
    created_at: datetime
    processed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
