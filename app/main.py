import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.services.outbox_relay import run_outbox_relay

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    relay = asyncio.create_task(run_outbox_relay())
    try:
        yield
    finally:
        relay.cancel()
        with suppress(asyncio.CancelledError):
            await relay


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
