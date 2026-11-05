import os
from pathlib import Path
from typing import Final, Optional

from httpx import AsyncClient, AsyncHTTPTransport, Timeout
from loguru import logger
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.migrate import (
    MigrationResult,
    flush_shop_redis,
    legacy_origin,
    migrate,
    preflight,
    upgrade_legacy_schema,
)
from app.cli.legacy.panel import fetch_panel_index
from app.cli.legacy.rollback import rollback
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


def oldest_pre_migration_backup(revision: str, directory: Path) -> Optional[Path]:
    found = directory.glob(f"{_BACKUP_PREFIX}{revision}_*.dump")
    return min(found, key=lambda p: p.stat().st_mtime, default=None)


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
    crypt_key = config.crypt_key.get_secret_value()
    try:
        async with engine.connect() as connection:
            revision = await current_revision(connection)
            original = await legacy_origin(connection)
        if revision not in LEGACY_REVISIONS or original is None:
            raise LegacyMigrationError(f"Nothing to migrate: database revision is {revision}")

        async with _panel_client(config) as client:
            sdk = RemnawaveSDK(client)
            await preflight(engine, sdk=sdk, crypt_key=crypt_key)

            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
            backup = BACKUP_DIR / f"{_BACKUP_PREFIX}{revision}_{stamp}.dump"
            await create_signed_database_dump(config, backup)
            print(f"Database saved to {backup}")

            panel_index = await fetch_panel_index(sdk)

        try:
            await upgrade_legacy_schema(engine)
            result = await migrate(
                engine,
                panel_index=panel_index,
                crypt_key=crypt_key,
                bot_owner_id=read_bot_owner_id(),
                original_revision=original,
            )
        except Exception as error:
            if not isinstance(error, LegacyMigrationError):
                logger.exception("Legacy migration failed")
            # the schema was already moved: whatever broke, the way back must be named
            advised = oldest_pre_migration_backup(original, BACKUP_DIR) or backup
            raise LegacyMigrationError(failure_message(error, original, advised)) from error
    finally:
        await engine.dispose()

    deliver_report(result, backup)
    await _flush_redis(config)


def failure_message(error: Exception, original: str, backup: Path) -> str:
    message = f"Migration failed: {error}. The old version ran on revision {original}."
    if original != LEGACY_HEAD:
        return (
            f"{message} Its schema may now be upgraded to {LEGACY_HEAD}, which the old image "
            f'will not start on: to go back, use "Restore backup" with {backup}. '
            "Or fix the cause and run the action again."
        )
    return f"{message} The old data is untouched. Fix the cause and run the action again."


async def _flush_redis(config: AppConfig) -> None:
    redis = Redis.from_url(config.redis.dsn)
    try:
        await flush_shop_redis(redis)
    except Exception as error:
        print(f"Warning: flushing the shop Redis failed ({error}). Run FLUSHDB on it manually.")
    finally:
        await redis.aclose()


def deliver_report(result: MigrationResult, backup: Path) -> None:
    print(render_report(result, backup, with_password=True))
    path = backup.with_suffix(".report.txt")
    try:
        path.write_text(render_report(result, backup, with_password=False))
    except OSError as error:
        print(f"Warning: writing the report to {path} failed ({error}).")


async def run_rollback(config: AppConfig) -> None:
    engine = create_engine(config)
    try:
        original = await rollback(engine)
    finally:
        await engine.dispose()
    # the new broker's list-typed `taskiq` key would break the old stream broker
    await _flush_redis(config)
    print(rollback_advice(original, BACKUP_DIR))


def rollback_advice(original: Optional[str], directory: Path) -> str:
    if original == LEGACY_HEAD:
        return "The database is back on the old schema: start the old image."
    if original is None:
        return (
            "The revision the old version ran on was not recorded. If it was below "
            f'{LEGACY_HEAD}, use "Restore backup" with the oldest pre-migration backup in '
            f"{directory}; otherwise start the old image."
        )
    backup = oldest_pre_migration_backup(original, directory)
    where = backup.name if backup is not None else f"the {original} pre-migration backup"
    return (
        f"The old version ran on revision {original}, but the database is now at "
        f'{LEGACY_HEAD}: the old image cannot start on it. Use "Restore backup" with '
        f"{where} instead, then start the old image."
    )
