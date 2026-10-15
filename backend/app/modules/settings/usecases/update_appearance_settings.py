from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.events import changed_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import AppearanceSettingsDto, UpdateAppearanceSettingsDto
from app.modules.settings.events import AppearanceSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository


class UpdateAppearanceSettingsUseCase(UseCase[UpdateAppearanceSettingsDto, AppearanceSettingsDto]):
    required_permission = Permission.APPEARANCE_SETTINGS_MANAGE

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(
        self, actor: Actor, data: UpdateAppearanceSettingsDto
    ) -> AppearanceSettingsDto:
        async with self._uow:
            before = await self._settings_repository.get_appearance_settings()
            settings = await self._settings_repository.update_appearance_settings(data)
            await self._event_publisher.publish(
                AppearanceSettingsChangedEvent(
                    actor=actor,
                    action="update",
                    changed_fields=changed_fields(before, settings, vars(data)),
                )
            )
        return settings
