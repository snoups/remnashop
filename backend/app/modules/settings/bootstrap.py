from app.core.config import AppConfig
from app.core.db.standalone import standalone_session
from app.modules.settings.dto import BotSettingsDto, UpdateOAuthSettingsDto
from app.modules.settings.repository import SettingsRepository


async def read_bot_settings(config: AppConfig) -> BotSettingsDto:
    # not the DI-managed engine: this runs before the process's dishka container
    # exists (telegram/__main__.py needs the token to even construct the Bot that
    # the container's context requires)
    async with standalone_session(config) as session:
        return await SettingsRepository(session).get_bot_settings()


async def enable_password_login(config: AppConfig) -> None:
    async with standalone_session(config) as session:
        await SettingsRepository(session).update_oauth_settings(
            UpdateOAuthSettingsDto(password_login_enabled=True)
        )
        await session.commit()
