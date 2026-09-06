from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings import SettingsRepository
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.publish import publish_translation_change
from app.modules.translations.repository import TranslationsRepository
from app.modules.translations.usecases._repush import repush_bot_commands_if_configured
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class ResetTranslationInput:
    locale: Locale
    message_id: str
    attribute_id: str


class ResetTranslationUseCase(UseCase[ResetTranslationInput, TranslationEntryDto]):
    required_permission = Permission.TRANSLATIONS_RESET

    def __init__(
        self,
        translations_repository: TranslationsRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        config: AppConfig,
        redis: Redis,
    ) -> None:
        self._translations_repository = translations_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._config = config
        self._redis = redis

    async def _execute(self, actor: UserDto, data: ResetTranslationInput) -> TranslationEntryDto:
        async with self._uow:
            reset = await self._translations_repository.reset_value(
                data.locale, data.message_id, data.attribute_id
            )

        await publish_translation_change(
            self._redis, data.locale, data.message_id, reset.value, attribute_id=data.attribute_id
        )

        await repush_bot_commands_if_configured(
            self._settings_repository, self._translations_repository, self._config
        )
        return reset
