import uuid
from typing import AsyncIterator, Awaitable, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.cli.legacy.schema import upgrade_legacy
from app.core.config import AppConfig


@pytest.fixture
async def legacy_engine(config: AppConfig) -> AsyncIterator[AsyncEngine]:
    name = f"remnashop_legacy_{uuid.uuid4().hex[:8]}"
    admin = create_async_engine(config.database.dsn, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{name}"'))
    database = config.database.model_copy(update={"name": name})
    engine = create_async_engine(database.dsn)
    try:
        yield engine
    finally:
        await engine.dispose()
        async with admin.connect() as connection:
            await connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        await admin.dispose()


@pytest.fixture
def legacy_at() -> Callable[[AsyncEngine, str], Awaitable[None]]:
    async def upgrade_to(engine: AsyncEngine, revision: str) -> None:
        async with engine.connect() as connection:
            await connection.run_sync(upgrade_legacy, revision)

    return upgrade_to
