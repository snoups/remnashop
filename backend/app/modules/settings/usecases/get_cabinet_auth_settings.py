from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import CabinetAuthSettingsDto
from app.modules.settings.repository import SettingsRepository


class GetCabinetAuthSettingsUseCase(UseCase[None, CabinetAuthSettingsDto]):
    required_permission = Permission.CABINET_AUTH_SETTINGS_VIEW

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> CabinetAuthSettingsDto:
        async with self._uow:
            return await self._settings_repository.get_cabinet_auth_settings()
