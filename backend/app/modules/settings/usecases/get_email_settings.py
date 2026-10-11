from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.dto import EmailSettingsDto
from app.modules.settings.repository import SettingsRepository


class GetEmailSettingsUseCase(UseCase[None, EmailSettingsDto]):
    required_permission = Permission.EMAIL_SETTINGS_VIEW

    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> EmailSettingsDto:
        async with self._uow:
            return await self._settings_repository.get_email_settings()
