from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import AppearanceSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class ResetAppearanceSettingsUseCase(UseCase[None, AppearanceSettingsDto]):
    required_permission = Permission.APPEARANCE_SETTINGS_RESET

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    # Images aren't touched here: they go through their own delete usecases,
    # so each keeps its own permission.
    async def _execute(self, actor: UserDto, data: None) -> AppearanceSettingsDto:
        async with self._uow:
            return await self._settings_repository.reset_appearance_settings()
