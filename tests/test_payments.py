from sqlalchemy import func, select

from app.core.config import get_settings
from app.models import Outbox

API_KEY = get_settings().api_key

PAYLOAD = {
    "amount": "100.00",
    "currency": "RUB",
    "description": "test payment",
    "metadata": {"order": "42"},
    "webhook_url": "https://example.com/hook",
}


def _headers(idempotency_key: str) -> dict[str, str]:
    return {"X-API-Key": API_KEY, "Idempotency-Key": idempotency_key}


async def test_create_payment_returns_202(client):
    resp = await client.post("/api/v1/payments", json=PAYLOAD, headers=_headers("k1"))

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "pending"
    assert body["payment_id"]


async def test_idempotency_same_key_returns_same_payment(client):
    r1 = await client.post("/api/v1/payments", json=PAYLOAD, headers=_headers("dup"))
    r2 = await client.post("/api/v1/payments", json=PAYLOAD, headers=_headers("dup"))

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["payment_id"] == r2.json()["payment_id"]


async def test_outbox_event_created(client, session_factory):
    await client.post("/api/v1/payments", json=PAYLOAD, headers=_headers("outbox"))

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(Outbox))

    assert count == 1


async def test_missing_api_key_returns_401(client):
    resp = await client.post(
        "/api/v1/payments",
        json=PAYLOAD,
        headers={"Idempotency-Key": "no-key"},
    )

    assert resp.status_code == 401


async def test_get_payment_returns_details(client):
    created = await client.post(
        "/api/v1/payments", json=PAYLOAD, headers=_headers("get")
    )
    payment_id = created.json()["payment_id"]

    resp = await client.get(
        f"/api/v1/payments/{payment_id}", headers={"X-API-Key": API_KEY}
    )

    assert resp.status_code == 200
    assert resp.json()["id"] == payment_id
    assert resp.json()["metadata"] == {"order": "42"}
