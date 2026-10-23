from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import AppearanceImageKind
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.modules.settings.appearance_storage import read_appearance_image
from app.modules.settings.dto import AppearanceImageDto
from app.modules.settings.repository import SettingsRepository


class GetPublicAppearanceImageUseCase:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._settings_repository = settings_repository
        self._config = config
        self._uow = uow

    async def execute(self, kind: AppearanceImageKind) -> AppearanceImageDto:
        async with self._uow:
            meta = await self._settings_repository.find_appearance_image_meta(kind)
            if meta is None:
                raise NotFoundError(
                    f"Appearance image not set: {kind}", code=ErrorCode.APPEARANCE_IMAGE_NOT_SET
                )

            extension, content_type = meta
            try:
                data = read_appearance_image(self._config.media_dir, kind, extension)
            except FileNotFoundError:
                raise NotFoundError(
                    f"Appearance image not set: {kind}", code=ErrorCode.APPEARANCE_IMAGE_NOT_SET
                ) from None

            return AppearanceImageDto(data=data, content_type=content_type)
