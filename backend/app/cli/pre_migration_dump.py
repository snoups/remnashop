import asyncio
import time
from pathlib import Path
from typing import Final, Optional

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.config import AppConfig
from app.core.constants import ALEMBIC_INI, DATETIME_FILE_FORMAT, TIME_1H
from app.core.db.standalone import standalone_session
from app.core.utils.time import datetime_now
from app.modules.backups import create_signed_database_dump

# Run by docker-entrypoint.sh before `alembic upgrade head`; a failure stops the migration.

# a migration failing in a restart loop dumps once, not on every restart; an older
# dump of the same revision may predate later changes, so it doesn't count
_REUSE_WITHIN_S: Final[int] = TIME_1H


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
    head = ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_current_head()
    current = await _current_revision(config)
    # a fresh database has nothing to lose, an up-to-date one nothing to migrate
    if current is None or current == head:
        return

    backup_dir = config.media_dir / "backups"
    if recent := _recent_dump(backup_dir, current):
        print(f"Keeping {recent}, made before an earlier attempt to migrate from '{current}'")
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
    # DATABASE_ prefix: the restore CLI lists these next to the scheduled dumps
    dest = backup_dir / f"DATABASE_pre-migration_{current}_{timestamp}.dump"
    await create_signed_database_dump(config, dest)
    print(f"Database saved to {dest} before migrating from '{current}' to '{head}'")


def _recent_dump(backup_dir: Path, revision: str) -> Optional[Path]:
    oldest = time.time() - _REUSE_WITHIN_S
    dumps = [
        path
        for path in backup_dir.glob(f"DATABASE_pre-migration_{revision}_*.dump")
        if path.stat().st_mtime >= oldest
    ]
    return max(dumps, key=lambda path: path.stat().st_mtime, default=None)


if __name__ == "__main__":
    asyncio.run(main())
