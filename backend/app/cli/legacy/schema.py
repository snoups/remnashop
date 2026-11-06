from pathlib import Path
from typing import Final, Optional

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.constants import ALEMBIC_INI

LEGACY_HEAD: Final[str] = "0046"
LEGACY_REVISIONS: Final[frozenset[str]] = frozenset(f"{number:04d}" for number in range(1, 47))
_MIGRATIONS_DIR: Final[Path] = Path(__file__).parent / "migrations"
# kept on the old schema: the revision the old image ran on, before our upgrade to LEGACY_HEAD
_ORIGIN_PREFIX: Final[str] = "remnashop-legacy-origin:"


def new_chain_revisions() -> frozenset[str]:
    """Every revision of this image's own chain, the head and those before it."""
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    return frozenset(revision.revision for revision in script.walk_revisions())


def upgrade_legacy(connection: Connection, revision: str = LEGACY_HEAD) -> None:
    """Commits after each migration, so the connection must have no open transaction."""
    if connection.in_transaction():
        raise RuntimeError("upgrade_legacy needs a connection with no open transaction")
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


async def recorded_origin(connection: AsyncConnection, schema: str) -> Optional[str]:
    comment: Optional[str] = await connection.scalar(
        text("SELECT obj_description(to_regnamespace(:schema), 'pg_namespace')"),
        {"schema": schema},
    )
    if comment is None or not comment.startswith(_ORIGIN_PREFIX):
        return None
    return comment.removeprefix(_ORIGIN_PREFIX)


async def record_origin(connection: AsyncConnection, schema: str, revision: str) -> None:
    if revision not in LEGACY_REVISIONS:
        raise ValueError(f"Not an old-version revision: {revision!r}")
    # COMMENT takes no bind parameters; the revision is checked above
    await connection.execute(
        text(f"COMMENT ON SCHEMA \"{schema}\" IS '{_ORIGIN_PREFIX}{revision}'")
    )
