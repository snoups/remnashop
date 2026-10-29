from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceTarget
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import AppearanceSettingsDto
from app.modules.settings.events import AppearanceSettingsChangedEvent
from app.modules.settings.repository import SettingsRepository


class ResetAppearanceSettingsUseCase(UseCase[AppearanceTarget, AppearanceSettingsDto]):
    required_permission = Permission.APPEARANCE_SETTINGS_RESET

    def __init__(
        self,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    # Images aren't touched here: they go through their own delete usecases,
    # so each keeps its own permission.
    async def _execute(self, actor: Actor, data: AppearanceTarget) -> AppearanceSettingsDto:
        async with self._uow:
            settings = await self._settings_repository.reset_appearance_settings(data)
            await self._event_publisher.publish(
                AppearanceSettingsChangedEvent(actor=actor, action="reset", target=data)
            )
        return settings
