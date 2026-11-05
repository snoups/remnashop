from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.cli.legacy.errors import LegacyMigrationError


async def _require_legacy(connection: AsyncConnection) -> None:
    found = await connection.scalar(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'legacy'")
    )
    if found is None:
        raise LegacyMigrationError("Schema 'legacy' does not exist: nothing to roll back")


async def rollback(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await _require_legacy(connection)
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("ALTER SCHEMA legacy RENAME TO public"))


async def drop_legacy(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await _require_legacy(connection)
        await connection.execute(text("DROP SCHEMA legacy CASCADE"))
