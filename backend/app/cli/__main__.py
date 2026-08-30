import asyncio
from typing import Final

from app.core.config import AppConfig
from app.modules.settings import enable_password_login

# Break-glass tool, run via `docker exec -it <api-container> python -m app.cli` --
# mirrors Remnawave's own built-in rescue CLI. Only one rescue action exists so
# far; more (reset password, restore backup) get their own menu entry here later.
_MENU: Final[str] = """Remnashop Rescue CLI
  1. Enable password authentication
  0. Exit
"""


async def _enable_password_login() -> None:
    config = AppConfig.get()
    await enable_password_login(config)
    print("Password authentication enabled.")


async def _run() -> None:
    print(_MENU)
    choice = input("> ").strip()

    if choice == "1":
        await _enable_password_login()
    elif choice == "0":
        pass
    else:
        print(f"Unknown option: {choice!r}")


if __name__ == "__main__":
    asyncio.run(_run())
