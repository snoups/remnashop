from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import BotCommandsSync, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import ActiveLocalesDto
from app.modules.translations.events import DefaultLocaleChangedEvent
from app.modules.translations.repository import TranslationRepository


class SetDefaultLocaleUseCase(UseCase[Locale, ActiveLocalesDto]):
    required_permission = Permission.LOCALES_DEFAULT_SET

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
            locales = await self._translation_repository.get_locales()
            if data == locales.default:
                return locales
            if data not in locales.active:
                raise ValidationError(
                    f"Locale not enabled: {data}", code=ErrorCode.LOCALE_NOT_ENABLED
                )
            await self._translation_repository.set_default_locale(data)
            locales = await self._translation_repository.get_locales()
            await self._event_publisher.publish(DefaultLocaleChangedEvent(actor=actor, locale=data))
        # the default locale's names also serve clients whose language has none
        await self._bot_commands.push()
        return locales
