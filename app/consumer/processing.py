import asyncio
import random

from app.core.config import get_settings

settings = get_settings()


class ProcessingError(Exception):
    """Эмуляция ошибки платёжного шлюза."""


async def emulate_processing() -> None:
    await asyncio.sleep(
        random.uniform(settings.processing_min_seconds, settings.processing_max_seconds)
    )
    if random.random() > settings.processing_success_rate:
        raise ProcessingError("emulated gateway failure")
