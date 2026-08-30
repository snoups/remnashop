from app.core.enums import Locale
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


class ListActiveLocalesUseCase(UseCase[None, list[Locale]]):
    required_permission = Permission.LOCALES_VIEW

    def __init__(self, settings_repository: SettingsRepository) -> None:
        self._settings_repository = settings_repository

    async def _execute(self, actor: UserDto, data: None) -> list[Locale]:
        return await self._settings_repository.list_active_locales()
