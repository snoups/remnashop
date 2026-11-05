from pathlib import Path
from typing import Final, Optional

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncConnection

LEGACY_HEAD: Final[str] = "0046"
LEGACY_REVISIONS: Final[frozenset[str]] = frozenset(f"{number:04d}" for number in range(1, 47))
_MIGRATIONS_DIR: Final[Path] = Path(__file__).parent / "migrations"


def upgrade_legacy(connection: Connection, revision: str = LEGACY_HEAD) -> None:
    config = Config()
    config.set_main_option("script_location", str(_MIGRATIONS_DIR))
    config.attributes["connection"] = connection
    command.upgrade(config, revision)


async def current_revision(connection: AsyncConnection, schema: str = "public") -> Optional[str]:
    exists = await connection.scalar(
        text("SELECT to_regclass(:name)"), {"name": f"{schema}.alembic_version"}
    )
    if exists is None:
        return None
    version: Optional[str] = await connection.scalar(
        text(f'SELECT version_num FROM "{schema}".alembic_version')
    )
    return version
