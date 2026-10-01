from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import AppearanceSettingsDto, UpdateAppearanceSettingsDto
from app.modules.settings.repository import SettingsRepository


class UpdateAppearanceSettingsUseCase(UseCase[UpdateAppearanceSettingsDto, AppearanceSettingsDto]):
    required_permission = Permission.APPEARANCE_SETTINGS_MANAGE

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: UpdateAppearanceSettingsDto
    ) -> AppearanceSettingsDto:
        async with self._uow:
            return await self._settings_repository.update_appearance_settings(data)
