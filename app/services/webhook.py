import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@retry(
    stop=stop_after_attempt(settings.webhook_max_attempts),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def _post(url: str, data: dict) -> None:
    async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
        response = await client.post(url, json=data)
        response.raise_for_status()


async def send_webhook(url: str, data: dict) -> None:
    try:
        await _post(url, data)
    except Exception as exc:  # noqa: BLE001
        logger.error("webhook failed for %s: %s", url, exc)