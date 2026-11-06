from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# pg_advisory_xact_lock key: every seed reads then inserts, and api instances,
# their uvicorn workers and telegram all seed on startup at the same time
_STARTUP_SEED_LOCK_KEY: Final[int] = 8221950


async def lock_startup_seeding(session: AsyncSession) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(_STARTUP_SEED_LOCK_KEY)))
