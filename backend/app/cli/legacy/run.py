import os
from pathlib import Path
from typing import Final, Optional

from httpx import AsyncClient, AsyncHTTPTransport, Timeout
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.migrate import (
    MigrationResult,
    flush_shop_redis,
    migrate,
    preflight,
    upgrade_legacy_schema,
)
from app.cli.legacy.panel import fetch_panel_index
from app.cli.legacy.schema import LEGACY_HEAD, LEGACY_REVISIONS, current_revision
from app.core.config import AppConfig
from app.core.constants import BACKUP_DIR, DATETIME_FILE_FORMAT
from app.core.db.standalone import connect_args
from app.core.resilient_transport import ResilientTransport
from app.core.utils.time import datetime_now
from app.modules.backups import create_signed_database_dump

_BACKUP_PREFIX: Final[str] = "DATABASE_pre-legacy-migration_"
_OWNER_ID_ENV: Final[str] = "BOT_OWNER_ID"
_CHECKLIST: Final[str] = """Next steps:
  - Keep APP_CRYPT_KEY in .env exactly as it was; take the new required variables from .env.example.
    The old BOT_TOKEN / BOT_SECRET_TOKEN are ignored: enter the bot token in the dashboard.
  - Replace compose and .env with the new ones, then run `up`.
  - Reverse proxy: the bot webhook /api/v1/telegram is now served by the remnashop-telegram
    container (port BOT_PORT, 5001), not by remnashop:5000. Payment and panel webhook paths
    are unchanged. Port 5001 was the database in the old compose: do not keep it alongside.
  - Grants of extra database roles on the old public schema are not carried over.
  - Sign in to the dashboard with the owner login above, then set the bot token and restart the bot.
  - Once everything works, run "Delete old-version data"."""


def read_bot_owner_id() -> Optional[int]:
    raw = os.environ.get(_OWNER_ID_ENV, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"Warning: {_OWNER_ID_ENV}={raw!r} is not a number, ignored.")
        return None


def create_engine(config: AppConfig) -> AsyncEngine:
    return create_async_engine(config.database.dsn, connect_args=connect_args(config.database))


def _panel_client(config: AppConfig) -> AsyncClient:
    panel = config.remnawave
    headers = {
        "Authorization": f"Bearer {panel.token.get_secret_value()}",
        "X-Api-Key": panel.caddy_token.get_secret_value(),
        "CF-Access-Client-Id": panel.cf_client_id.get_secret_value(),
        "CF-Access-Client-Secret": panel.cf_client_secret.get_secret_value(),
    }
    if not panel.is_external:
        headers["x-forwarded-proto"] = "https"
        headers["x-forwarded-for"] = "127.0.0.1"
    # reads only: the Redis-backed PanelWriteRecorder tracks our writes, and this makes none
    return AsyncClient(
        base_url=f"{panel.url.get_secret_value()}/api",
        headers=headers,
        cookies=panel.cookies,
        timeout=Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
        transport=ResilientTransport(AsyncHTTPTransport()),
    )


def newest_pre_migration_backup(directory: Path = BACKUP_DIR) -> Optional[Path]:
    found = sorted(directory.glob(f"{_BACKUP_PREFIX}*.dump"), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


def backup_revision(path: Path) -> str:
    return path.name.removeprefix(_BACKUP_PREFIX).split("_", 1)[0]


def render_report(result: MigrationResult, backup: Path, *, with_password: bool) -> str:
    lines = [
        result.report.render(),
        "",
        f"Original revision: {result.original_revision}",
        f"Pre-migration backup: {backup}",
    ]
    if result.owner is not None:
        lines.append(f"Owner login: {result.owner.login}")
        if with_password:
            lines.append(
                f"Owner password (shown once, change it at first sign-in): {result.owner.password}"
            )
    else:
        lines.append("No owner was migrated: create one from the dashboard (bootstrap).")
    lines += ["", _CHECKLIST]
    return "\n".join(lines)


async def run_migration(config: AppConfig) -> None:
    engine = create_engine(config)
    try:
        async with engine.connect() as connection:
            revision = await current_revision(connection)
        if revision not in LEGACY_REVISIONS:
            raise LegacyMigrationError(f"Nothing to migrate: database revision is {revision}")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
        backup = BACKUP_DIR / f"{_BACKUP_PREFIX}{revision}_{stamp}.dump"
        await create_signed_database_dump(config, backup)
        print(f"Database saved to {backup}")

        crypt_key = config.crypt_key.get_secret_value()
        async with _panel_client(config) as client:
            sdk = RemnawaveSDK(client)
            await preflight(engine, sdk=sdk, crypt_key=crypt_key)
            original = await upgrade_legacy_schema(engine)
            try:
                result = await migrate(
                    engine,
                    panel_index=await fetch_panel_index(sdk),
                    crypt_key=crypt_key,
                    bot_owner_id=read_bot_owner_id(),
                    original_revision=original,
                )
            except Exception:
                print(
                    f"Migration failed. The old schema is kept (upgraded to {LEGACY_HEAD}), "
                    f"nothing was lost. Backup: {backup}. Fix the cause and run the action again."
                )
                raise
    finally:
        await engine.dispose()

    deliver_report(result, backup)
    redis = Redis.from_url(config.redis.dsn)
    try:
        await flush_shop_redis(redis)
    except Exception as error:
        print(f"Warning: flushing the shop Redis failed ({error}). Run FLUSHDB on it manually.")
    finally:
        await redis.aclose()


def deliver_report(result: MigrationResult, backup: Path) -> None:
    backup.with_suffix(".report.txt").write_text(render_report(result, backup, with_password=False))
    print(render_report(result, backup, with_password=True))


def rollback_advice(directory: Path = BACKUP_DIR) -> str:
    backup = newest_pre_migration_backup(directory)
    if backup is None:
        return "No pre-migration backup found in the backup directory."
    original = backup_revision(backup)
    if original != LEGACY_HEAD:
        return (
            f"The old version ran on revision {original}, but the database is now at "
            f'{LEGACY_HEAD}: the old image cannot start on it. Use "Restore backup" with '
            f"{backup.name} instead, then start the old image."
        )
    return "The database is back on the old schema: start the old image."
