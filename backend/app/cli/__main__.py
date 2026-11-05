import asyncio
from collections.abc import Awaitable
from pathlib import Path
from typing import Final

from app.cli.audit import record_rescue
from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.rollback import drop_legacy
from app.cli.legacy.run import create_engine, run_migration, run_rollback
from app.cli.reset_owner_access import OwnerNotRegisteredError, reset_owner_access
from app.cli.restore_backup import list_database_backups, run_restore
from app.core.config import AppConfig
from app.core.db.crypt_key import reset_encrypted_secrets
from app.core.db.standalone import standalone_session
from app.modules.settings import enable_password_login

# Break-glass tool, run via `docker compose run --rm remnashop cli`.
_MENU: Final[str] = """Remnashop Rescue CLI
    1. Enable password authentication
    2. Restore backup
    3. Reset owner access (new password, clear IP allowlist)
    4. Reset encrypted secrets (after APP_CRYPT_KEY changed)
    5. Migrate data from the old version
    6. Roll back the migration
    7. Delete old-version data
    0. Exit
"""


async def _enable_password_login() -> None:
    config = AppConfig.get()
    await enable_password_login(config)
    async with standalone_session(config) as session:
        await record_rescue(session, "enable_password_login")
        await session.commit()
    print("Password authentication enabled.")


async def _reset_owner_access() -> None:
    if not _confirm(
        "This resets the owner's password, clears their IP allowlist, signs them out "
        "everywhere and removes their passkeys, linked OAuth accounts and Telegram (API "
        "tokens are kept). Continue?"
    ):
        print("Aborted.")
        return

    config = AppConfig.get()
    async with standalone_session(config) as session:
        try:
            result = await reset_owner_access(session, config.crypt_key.get_secret_value())
        except OwnerNotRegisteredError:
            print(
                "The owner hasn't registered yet: open the dashboard and "
                "register the owner account."
            )
            return

    if result is None:
        print("No owner exists yet -- bootstrap one from the dashboard.")
        return

    # a new password is useless if password login itself is switched off
    await enable_password_login(config)
    owner, password = result
    print(f"Owner access reset. Login: {owner.login}")
    print(f"New password: {password}")
    print("Telegram was unlinked from the owner; connect it again from the dashboard.")


async def _reset_encrypted_secrets() -> None:
    if not _confirm(
        "This erases every secret stored in the database: the bot token and proxy, payment "
        "gateway credentials (gateways are switched off), OAuth clients, SMTP passwords, the "
        "captcha secret and the web push keys. Enter them in the dashboard again afterwards. "
        "Continue?"
    ):
        print("Aborted.")
        return

    async with standalone_session(AppConfig.get()) as session:
        await reset_encrypted_secrets(session)
        await record_rescue(session, "reset_encrypted_secrets")
        await session.commit()
    print("Encrypted secrets cleared. Restart the containers, then enter the secrets again.")
    print('Staff passwords are peppered with the same key: use "Reset owner access" too.')


def _confirm(prompt: str) -> bool:
    return input(f"{prompt} [yes/N]: ").strip().lower() == "yes"


async def _restore_backup() -> None:
    backups = list_database_backups(AppConfig.get().media_dir / "backups")

    if backups:
        print("Available database backups:")
        for i, path in enumerate(backups, start=1):
            print(f"  {i}. {path.name}")
        print("  0. Enter a custom path")

        choice = input("> ").strip()
        if choice == "0":
            path = Path(input("Path to .dump file: ").strip())
        else:
            try:
                path = backups[int(choice) - 1]
            except (ValueError, IndexError):
                print(f"Unknown option: {choice!r}")
                return
    else:
        print("No database backups found in the backup directory.")
        path = Path(input("Path to .dump file: ").strip())

    if not path.exists():
        print(f"File not found: {path}")
        return

    await run_restore(
        path,
        config=AppConfig.get(),
        confirm_foreign=lambda: _confirm(
            "This archive is not verified as produced by this deployment. Continue?"
        ),
        confirm_start=lambda: _confirm(
            "This will TERMINATE other database connections and OVERWRITE the current "
            "database. Continue?"
        ),
    )


async def _migrate_legacy() -> None:
    if not _confirm(
        "This moves the old version's data to the new schema (the old data is kept in schema "
        "'legacy', a signed backup is made first). The panel must be Remnawave 3.x and "
        "APP_CRYPT_KEY the old one. Stop the shop containers first (`docker compose stop` "
        "everything except the database). Continue?"
    ):
        print("Aborted.")
        return
    await _legacy_action(run_migration(AppConfig.get()))


async def _legacy_action(action: Awaitable[None]) -> bool:
    try:
        await action
    except LegacyMigrationError as error:
        print(f"Stopped: {error}")
        return False
    return True


async def _rollback_legacy() -> None:
    if not _confirm("This DROPS the new schema and brings the old data back. Continue?"):
        print("Aborted.")
        return
    await _legacy_action(run_rollback(AppConfig.get()))


async def _delete_legacy() -> None:
    if not _confirm("This permanently deletes the old version's data (schema 'legacy'). Continue?"):
        print("Aborted.")
        return
    engine = create_engine(AppConfig.get())
    try:
        done = await _legacy_action(drop_legacy(engine))
    finally:
        await engine.dispose()
    if done:
        print("Old-version data deleted.")


async def _run() -> None:
    print(_MENU)
    choice = input("> ").strip()

    if choice == "1":
        await _enable_password_login()
    elif choice == "2":
        await _restore_backup()
    elif choice == "3":
        await _reset_owner_access()
    elif choice == "4":
        await _reset_encrypted_secrets()
    elif choice == "5":
        await _migrate_legacy()
    elif choice == "6":
        await _rollback_legacy()
    elif choice == "7":
        await _delete_legacy()
    elif choice == "0":
        pass
    else:
        print(f"Unknown option: {choice!r}")


if __name__ == "__main__":
    asyncio.run(_run())
