import asyncio
import sys
from enum import StrEnum
from typing import Final, Optional

from sqlalchemy.ext.asyncio import create_async_engine

from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.run import run_auto_migration
from app.cli.legacy.schema import LEGACY_REVISIONS, current_revision, new_chain_revisions
from app.core.config import AppConfig
from app.core.db.standalone import connect_args
from app.core.logger import setup_logger

# Run first by docker-entrypoint.sh's api branch, ahead of the pre-migration dump.

_NEWER_MESSAGE: Final[str] = (
    "The database belongs to a newer release than this image (revision {revision}): "
    "run that release or restore a backup."
)


class StartAction(StrEnum):
    START = "START"
    MIGRATE = "MIGRATE"
    REFUSE = "REFUSE"


def start_action(revision: Optional[str], new_revisions: frozenset[str]) -> StartAction:
    if revision is None or revision in new_revisions:
        return StartAction.START
    if revision in LEGACY_REVISIONS:
        return StartAction.MIGRATE
    # an unknown revision would loop the pre-migration dump and alembic on every restart
    return StartAction.REFUSE


async def _revision(config: AppConfig) -> Optional[str]:
    engine = create_async_engine(config.database.dsn, connect_args=connect_args(config.database))
    try:
        async with engine.connect() as connection:
            return await current_revision(connection)
    finally:
        await engine.dispose()


async def _guard(config: AppConfig) -> None:
    revision = await _revision(config)
    action = start_action(revision, new_chain_revisions())
    if action is StartAction.REFUSE:
        raise LegacyMigrationError(_NEWER_MESSAGE.format(revision=revision))
    if action is StartAction.MIGRATE:
        print(f"The database belongs to the old version (revision {revision}): migrating it")
        await run_auto_migration(config)


def main() -> None:
    config = AppConfig.get()
    # loguru's default sink prints frame locals: the crypt key and decrypted secrets
    setup_logger(config, "api")
    try:
        asyncio.run(_guard(config))
    except LegacyMigrationError as error:
        print(f"Stopped: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
