import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.config import get_settings
from app.db.session import get_session

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(api_key_header)) -> str:
    if api_key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Key")

    if not secrets.compare_digest(get_settings().api_key.encode(), api_key.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED)

    return api_key


__all__ = ["get_session", "require_api_key"]

DbSession = Annotated[AsyncSession, Depends(get_session)]
ApiKey = Annotated[str, Depends(require_api_key)]
