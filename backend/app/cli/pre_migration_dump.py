import asyncio
from pathlib import Path
from typing import Final, Optional

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.config import AppConfig
from app.core.constants import BACKUP_DIR, BASE_DIR, DATETIME_FILE_FORMAT
from app.core.db.standalone import standalone_session
from app.core.utils.time import datetime_now
from app.modules.backups import create_signed_database_dump

# Run by docker-entrypoint.sh before `alembic upgrade head`; a failure stops the migration.

_ALEMBIC_INI: Final[Path] = BASE_DIR / "alembic.ini"


async def _current_revision(config: AppConfig) -> Optional[str]:
    async with standalone_session(config) as session:
        if await session.scalar(text("SELECT to_regclass('alembic_version')")) is None:
            return None
        version: Optional[str] = await session.scalar(
            text("SELECT version_num FROM alembic_version")
        )
        return version


async def main() -> None:
    config = AppConfig.get()
    head = ScriptDirectory.from_config(Config(str(_ALEMBIC_INI))).get_current_head()
    current = await _current_revision(config)
    # a fresh database has nothing to lose, an up-to-date one nothing to migrate
    if current is None or current == head:
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
    # DATABASE_ prefix: the restore CLI lists these next to the scheduled dumps
    dest = BACKUP_DIR / f"DATABASE_pre-migration_{current}_{timestamp}.dump"
    await create_signed_database_dump(config, dest)
    print(f"Database saved to {dest} before migrating from '{current}' to '{head}'")


if __name__ == "__main__":
    asyncio.run(main())
