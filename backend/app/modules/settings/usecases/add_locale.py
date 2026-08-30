from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.events import LocaleActivatedEvent
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class AddLocaleUseCase(UseCase[Locale, list[Locale]]):
    required_permission = Permission.LOCALES_ADD

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: Locale) -> list[Locale]:
        async with self._uow:
            await self._settings_repository.add_active_locale(data)
            locales = await self._settings_repository.list_active_locales()

        await self._event_publisher.publish(LocaleActivatedEvent(locale=data))
        return locales
