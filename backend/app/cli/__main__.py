import asyncio
from pathlib import Path
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.cli.reset_owner_access import reset_owner_access
from app.cli.restore_backup import list_database_backups, run_restore
from app.core.config import AppConfig
from app.modules.settings import enable_password_login

# Break-glass tool, run via `docker exec -it <api-container> python -m app.cli`.
_MENU: Final[str] = """Remnashop Rescue CLI
    1. Enable password authentication
    2. Restore backup
    3. Reset owner access (new password, clear IP allowlist)
    0. Exit
"""


async def _enable_password_login() -> None:
    config = AppConfig.get()
    await enable_password_login(config)
    print("Password authentication enabled.")


async def _reset_owner_access() -> None:
    if not _confirm(
        "This resets the owner's password, clears their IP allowlist, signs them out "
        "everywhere and removes their passkeys and linked OAuth accounts (API tokens "
        "are kept). Continue?"
    ):
        print("Aborted.")
        return

    config = AppConfig.get()
    engine = create_async_engine(config.database.dsn)
    try:
        async with AsyncSession(engine) as session:
            result = await reset_owner_access(session, config.crypt_key.get_secret_value())
    finally:
        await engine.dispose()

    if result is None:
        print("No owner exists yet -- bootstrap one from the dashboard.")
        return

    # a new password is useless if password login itself is switched off
    await enable_password_login(config)
    owner, password = result
    print(f"Owner access reset. Login: {owner.login}")
    print(f"New password: {password}")


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


async def _run() -> None:
    print(_MENU)
    choice = input("> ").strip()

    if choice == "1":
        await _enable_password_login()
    elif choice == "2":
        await _restore_backup()
    elif choice == "3":
        await _reset_owner_access()
    elif choice == "0":
        pass
    else:
        print(f"Unknown option: {choice!r}")


if __name__ == "__main__":
    asyncio.run(_run())
