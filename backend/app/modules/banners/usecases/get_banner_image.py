from app.core.config import AppConfig
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.dto import BannerKeyDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import read_banner_file
from app.modules.users import UserDto


class GetBannerImageUseCase(UseCase[BannerKeyDto, tuple[bytes, str]]):
    required_permission = Permission.BANNERS_IMAGE_VIEW

    def __init__(self, banner_repository: BannerRepository, config: AppConfig) -> None:
        self._banner_repository = banner_repository
        self._config = config

    async def _execute(self, actor: UserDto, data: BannerKeyDto) -> tuple[bytes, str]:
        banner = await self._banner_repository.get(data.name, data.locale)
        if banner is None:
            raise NotFoundError(f"Banner not found: {data.name}/{data.locale}")

        try:
            image_data = read_banner_file(
                self._config.media_dir, banner.name, banner.locale, banner.extension
            )
        except FileNotFoundError:
            raise NotFoundError(f"Banner not found: {data.name}/{data.locale}") from None

        return image_data, banner.content_type
