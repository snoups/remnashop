from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.dto import BannerKeyDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import read_banner_file


class GetBannerImageUseCase(UseCase[BannerKeyDto, tuple[bytes, str]]):
    required_permission = Permission.BANNERS_IMAGE_VIEW

    def __init__(
        self,
        banner_repository: BannerRepository,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._banner_repository = banner_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: Actor, data: BannerKeyDto) -> tuple[bytes, str]:
        async with self._uow:
            banner = await self._banner_repository.get(data.name, data.locale)
            if banner is None:
                raise NotFoundError(
                    f"Banner not found: {data.name}/{data.locale}", code=ErrorCode.BANNER_NOT_FOUND
                )

            try:
                image_data = read_banner_file(
                    self._config.media_dir, banner.name, banner.locale, banner.extension
                )
            except FileNotFoundError:
                raise NotFoundError(
                    f"Banner not found: {data.name}/{data.locale}", code=ErrorCode.BANNER_NOT_FOUND
                ) from None

            return image_data, banner.content_type
