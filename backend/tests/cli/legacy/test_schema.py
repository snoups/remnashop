from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.cli.legacy.schema import LEGACY_HEAD, current_revision, upgrade_legacy

_COLUMN_SQL = (
    "SELECT 1 FROM information_schema.columns WHERE table_name = :table AND column_name = :column"
)


async def test_upgrade_from_empty_reaches_head(legacy_engine: AsyncEngine) -> None:
    async with legacy_engine.connect() as connection:
        assert await current_revision(connection) is None
        await connection.rollback()
        await connection.run_sync(upgrade_legacy)
        assert await current_revision(connection) == LEGACY_HEAD
        for table in ("users", "subscriptions", "transactions"):
            assert await connection.scalar(text("SELECT to_regclass(:t)"), {"t": table})
        assert await connection.scalar(
            text(_COLUMN_SQL), {"table": "users", "column": "token_version"}
        )


async def test_upgrade_from_0039_reaches_head(legacy_engine: AsyncEngine, legacy_at) -> None:  # type: ignore[no-untyped-def]
    await legacy_at(legacy_engine, "0039")
    async with legacy_engine.connect() as connection:
        assert await current_revision(connection) == "0039"
        assert not await connection.scalar(
            text(_COLUMN_SQL), {"table": "subscriptions", "column": "grace_until"}
        )
        await connection.rollback()
        await connection.run_sync(upgrade_legacy)
        assert await current_revision(connection) == LEGACY_HEAD
        assert await connection.scalar(
            text(_COLUMN_SQL), {"table": "subscriptions", "column": "grace_until"}
        )
