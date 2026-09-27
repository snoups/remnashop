from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.events import LocaleDeactivatedEvent
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class RemoveLocaleUseCase(UseCase[Locale, list[Locale]]):
    required_permission = Permission.LOCALES_REMOVE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        config: AppConfig,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._config = config

    async def _execute(self, actor: UserDto, data: Locale) -> list[Locale]:
        # The default locale is the TranslatorHub's root_locale -- deactivating
        # it leaves the hub with no root translator, and read_translator_hub()
        # runs before uvicorn.run() in telegram/__main__.py, so the process
        # would crash on every start instead of just losing one language.
        if data == self._config.default_locale:
            raise ValidationError(f"The default locale ({data.value}) cannot be removed")

        async with self._uow:
            await self._settings_repository.remove_active_locale(data)
            locales = await self._settings_repository.list_active_locales()
            await self._event_publisher.publish(LocaleDeactivatedEvent(actor=actor, locale=data))
        return locales
