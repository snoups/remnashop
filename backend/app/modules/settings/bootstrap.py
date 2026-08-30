from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import AppConfig
from app.modules.settings.dto import BotSettingsDto, UpdateOAuthSettingsDto
from app.modules.settings.repository import SettingsRepository


async def read_bot_settings(config: AppConfig) -> BotSettingsDto:
    # Standalone engine, not the DI-managed one: this runs before the process's
    # dishka container exists (telegram/__main__.py needs the token to even
    # construct the Bot that the container's context requires).
    engine = create_async_engine(config.database.dsn)

    try:
        async with AsyncSession(engine) as session:
            return await SettingsRepository(session).get_bot_settings()
    finally:
        await engine.dispose()


async def enable_password_login(config: AppConfig) -> None:
    # Same standalone-engine rationale as read_bot_settings() -- app/cli runs
    # outside the normal dishka-managed process lifecycle entirely.
    engine = create_async_engine(config.database.dsn)

    try:
        async with AsyncSession(engine) as session:
            await SettingsRepository(session).update_oauth_settings(
                UpdateOAuthSettingsDto(password_login_enabled=True)
            )
            await session.commit()
    finally:
        await engine.dispose()
