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
