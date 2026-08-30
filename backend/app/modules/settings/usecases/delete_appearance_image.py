from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceImageKind
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings.appearance_storage import delete_appearance_image
from app.modules.settings.dto import AppearanceSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.users import UserDto


async def _delete_appearance_image(
    settings_repository: SettingsRepository,
    config: AppConfig,
    uow: UnitOfWork,
    kind: AppearanceImageKind,
) -> AppearanceSettingsDto:
    meta = await settings_repository.get_appearance_image_meta(kind)
    if meta is None:
        raise NotFoundError(f"Appearance image not set: {kind}")

    async with uow:
        settings = await settings_repository.clear_appearance_image(kind)
    delete_appearance_image(config.media_dir, kind, meta[0])
    return settings


class DeleteAppearanceLogoUseCase(UseCase[None, AppearanceSettingsDto]):
    required_permission = Permission.APPEARANCE_LOGO_DELETE

    def __init__(
        self, settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> AppearanceSettingsDto:
        return await _delete_appearance_image(
            self._settings_repository, self._config, self._uow, AppearanceImageKind.LOGO
        )


class DeleteAppearanceFaviconUseCase(UseCase[None, AppearanceSettingsDto]):
    required_permission = Permission.APPEARANCE_FAVICON_DELETE

    def __init__(
        self, settings_repository: SettingsRepository, config: AppConfig, uow: UnitOfWork
    ) -> None:
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> AppearanceSettingsDto:
        return await _delete_appearance_image(
            self._settings_repository, self._config, self._uow, AppearanceImageKind.FAVICON
        )
