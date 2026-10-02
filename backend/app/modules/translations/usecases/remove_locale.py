from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import BotCommandsSync, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.events import LocaleDeactivatedEvent
from app.modules.translations.repository import TranslationRepository


class RemoveLocaleUseCase(UseCase[Locale, list[Locale]]):
    required_permission = Permission.LOCALES_REMOVE

    def __init__(
        self,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        bot_commands: BotCommandsSync,
        config: AppConfig,
    ) -> None:
        self._translation_repository = translation_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._bot_commands = bot_commands
        self._config = config

    async def _execute(self, actor: Actor, data: Locale) -> list[Locale]:
        # The default locale is the TranslatorHub's root_locale -- deactivating
        # it leaves the hub with no root translator, and read_translator_hub()
        # runs before uvicorn.run() in telegram/__main__.py, so the process
        # would crash on every start instead of just losing one language.
        if data == self._config.default_locale:
            raise ValidationError(
                f"The default locale ({data.value}) cannot be removed",
                code=ErrorCode.LOCALE_DEFAULT_NOT_REMOVABLE,
            )

        async with self._uow:
            await self._translation_repository.remove_active_locale(data)
            locales = await self._translation_repository.list_active_locales()
            await self._event_publisher.publish(LocaleDeactivatedEvent(actor=actor, locale=data))
        await self._bot_commands.drop_locale(data)
        return locales
