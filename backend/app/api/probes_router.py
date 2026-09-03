import asyncio
from typing import Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

router = APIRouter(include_in_schema=False)

_READYZ_TIMEOUT_S: Final[float] = 2.0


async def _probe_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def _probe_redis(redis: Redis) -> None:
    await redis.ping()  # type: ignore[misc]


async def _is_ready(engine: AsyncEngine, redis: Redis) -> bool:
    try:
        async with asyncio.timeout(_READYZ_TIMEOUT_S):
            await _probe_database(engine)
            await _probe_redis(redis)
    except Exception:
        logger.warning("Readiness probe failed")
        return False
    return True


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
@inject
async def readyz(engine: FromDishka[AsyncEngine], redis: FromDishka[Redis]) -> JSONResponse:
    if await _is_ready(engine, redis):
        return JSONResponse(content={"status": "ready"})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "not ready"}
    )
