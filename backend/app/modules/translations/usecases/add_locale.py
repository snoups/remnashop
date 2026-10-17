from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import ActiveLocalesDto
from app.modules.translations.events import LocaleActivatedEvent
from app.modules.translations.ports import BotCommandsSync
from app.modules.translations.repository import TranslationRepository


class AddLocaleUseCase(UseCase[Locale, ActiveLocalesDto]):
    required_permission = Permission.LOCALES_ADD

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
            # PUT semantics: re-adding is a no-op, not a re-copy over edited translations
            if data in await self._translation_repository.list_active_locales():
                return await self._translation_repository.get_locales()
            await self._translation_repository.add_active_locale(data)
            # in the same transaction, not a worker task: the dashboard re-reads
            # the translations right away and would find the new locale empty
            await self._translation_repository.copy_locale_from(Locale.EN, data)
            locales = await self._translation_repository.get_locales()
            await self._event_publisher.publish(LocaleActivatedEvent(actor=actor, locale=data))
        await self._bot_commands.push()
        return locales
