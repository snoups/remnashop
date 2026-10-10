from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.uow import UnitOfWork
from app.modules.settings.bot_commands_sync import BotCommandsPusher
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases.get_bot_commands import GetBotCommandsUseCase
from app.modules.translations.repository import TranslationRepository


def make_bot_commands_sync(session: AsyncSession, uow: UnitOfWork) -> BotCommandsPusher:
    settings_repository = SettingsRepository(session)
    return BotCommandsPusher(
        settings_repository,
        TranslationRepository(session),
        GetBotCommandsUseCase(settings_repository, uow),
        uow,
    )


# every UpdateShopSettingsDto field, for tests that write the whole row
SHOP_SETTINGS_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "max_active_subscriptions",
        "device_single_reset_enabled",
        "device_single_reset_cooldown_hours",
        "device_all_reset_enabled",
        "device_all_reset_cooldown_hours",
        "link_reset_enabled",
        "link_reset_cooldown_hours",
    }
)
