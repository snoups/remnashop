from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import AppConfig
from app.core.config.database import DatabaseConfig


def connect_args(database: DatabaseConfig) -> dict[str, Any]:
    return {
        "server_settings": {
            # compile time outweighs the gain on our short queries and mid-size aggregates
            "jit": "off",
            # NOW_FUNC writes a zoneless UTC timestamp into timestamptz columns,
            # read in the session's zone: pinned, so the server default can't shift it
            "timezone": "UTC",
            "statement_timeout": str(database.statement_timeout_ms),
            "idle_in_transaction_session_timeout": str(database.idle_in_transaction_timeout_ms),
        },
        "command_timeout": database.command_timeout_s,
        "timeout": database.connect_timeout_s,
    }


@asynccontextmanager
async def standalone_session(config: AppConfig) -> AsyncIterator[AsyncSession]:
    # for code that runs without a dishka container: process bootstrap, the CLI
    engine = create_async_engine(config.database.dsn, connect_args=connect_args(config.database))
    try:
        async with AsyncSession(engine, expire_on_commit=False, autoflush=False) as session:
            yield session
    finally:
        await engine.dispose()
