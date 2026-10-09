from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import BotCommandsSync, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import ActiveLocalesDto
from app.modules.translations.events import LocaleDeactivatedEvent
from app.modules.translations.repository import TranslationRepository


class RemoveLocaleUseCase(UseCase[Locale, ActiveLocalesDto]):
    required_permission = Permission.LOCALES_REMOVE

    def __init__(
        self,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        bot_commands: BotCommandsSync,
    ) -> None:
        self._translation_repository = translation_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._bot_commands = bot_commands

    async def _execute(self, actor: Actor, data: Locale) -> ActiveLocalesDto:
        async with self._uow:
            # the default locale is the TranslatorHub's root_locale; without it
            # read_translator_hub() fails and the telegram process crashes on start
            if data == await self._translation_repository.get_default_locale():
                raise ValidationError(
                    f"The default locale ({data.value}) cannot be removed",
                    code=ErrorCode.LOCALE_DEFAULT_NOT_REMOVABLE,
                )
            await self._translation_repository.remove_active_locale(data)
            locales = await self._translation_repository.get_locales()
            await self._event_publisher.publish(LocaleDeactivatedEvent(actor=actor, locale=data))
        await self._bot_commands.drop_locale(data)
        return locales
