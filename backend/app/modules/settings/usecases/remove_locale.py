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
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: Locale) -> list[Locale]:
        if data == Locale.EN:
            raise ValidationError("The en locale cannot be removed")

        async with self._uow:
            await self._settings_repository.remove_active_locale(data)
            locales = await self._settings_repository.list_active_locales()
            await self._event_publisher.publish(LocaleDeactivatedEvent(locale=data))
        return locales
