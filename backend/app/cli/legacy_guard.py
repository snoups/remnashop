import asyncio
import sys
from typing import Final, Optional

from sqlalchemy.ext.asyncio import create_async_engine

from app.cli.legacy.schema import LEGACY_REVISIONS, current_revision
from app.core.config import AppConfig
from app.core.db.standalone import connect_args

# Run first by docker-entrypoint.sh's api branch, ahead of the pre-migration dump.

_MESSAGE: Final[str] = (
    "The database belongs to the old version (revision {revision}). Migrate it first: run "
    '`docker compose run --rm remnashop cli` and pick "Migrate data from the old version".'
)


def legacy_guard_message(revision: Optional[str]) -> Optional[str]:
    if revision in LEGACY_REVISIONS:
        return _MESSAGE.format(revision=revision)
    return None


async def _revision(config: AppConfig) -> Optional[str]:
    engine = create_async_engine(config.database.dsn, connect_args=connect_args(config.database))
    try:
        async with engine.connect() as connection:
            return await current_revision(connection)
    finally:
        await engine.dispose()


def main() -> None:
    message = legacy_guard_message(asyncio.run(_revision(AppConfig.get())))
    if message is not None:
        print(message, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
