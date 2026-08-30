from app.modules.settings.dto import AppearanceSettingsDto
from app.modules.settings.repository import SettingsRepository


class GetPublicAppearanceUseCase:
    def __init__(self, settings_repository: SettingsRepository) -> None:
        self._settings_repository = settings_repository

    async def execute(self) -> AppearanceSettingsDto:
        return await self._settings_repository.get_appearance_settings()
