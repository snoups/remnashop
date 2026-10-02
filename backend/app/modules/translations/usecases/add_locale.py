from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.ports import BotCommandsSync, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.events import LocaleActivatedEvent
from app.modules.translations.repository import TranslationRepository


class AddLocaleUseCase(UseCase[Locale, list[Locale]]):
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

    async def _execute(self, actor: Actor, data: Locale) -> list[Locale]:
        async with self._uow:
            # PUT semantics: re-adding is a no-op, not a re-copy over edited translations
            locales = await self._translation_repository.list_active_locales()
            if data in locales:
                return locales
            await self._translation_repository.add_active_locale(data)
            # In the same transaction, not a worker task: the dashboard
            # re-reads the translations right after this returns, and an
            # async copy loses that race -- the new locale reads as empty.
            await self._translation_repository.copy_locale_from(Locale.EN, data)
            locales = await self._translation_repository.list_active_locales()
            await self._event_publisher.publish(LocaleActivatedEvent(actor=actor, locale=data))
        await self._bot_commands.push()
        return locales
