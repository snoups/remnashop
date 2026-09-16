from app.core.db.uow import UnitOfWork
from app.modules.settings.dto import AppearanceSettingsDto
from app.modules.settings.repository import SettingsRepository


class GetPublicAppearanceUseCase:
    def __init__(self, settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
        self._settings_repository = settings_repository
        self._uow = uow

    async def execute(self) -> AppearanceSettingsDto:
        async with self._uow:
            return await self._settings_repository.get_appearance_settings()
