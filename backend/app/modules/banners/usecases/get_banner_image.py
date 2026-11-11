from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.dto import BannerImageDto, BannerImageQueryDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.storage import read_banner_file
from app.modules.translations import TranslationRepository


class GetBannerImageUseCase(UseCase[BannerImageQueryDto, BannerImageDto]):
    required_permission = Permission.BANNERS_IMAGE_VIEW

    def __init__(
        self,
        banner_repository: BannerRepository,
        translation_repository: TranslationRepository,
        config: AppConfig,
        uow: UnitOfWork,
    ) -> None:
        self._banner_repository = banner_repository
        self._translation_repository = translation_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: Actor, data: BannerImageQueryDto) -> BannerImageDto:
        async with self._uow:
            if data.fallback:
                default_locale = await self._translation_repository.get_default_locale()
                banner = await self._banner_repository.find_for_display(
                    data.name, data.locale, default_locale
                )
            else:
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

            return BannerImageDto(
                data=image_data,
                content_type=banner.content_type,
                name=banner.name,
                locale=banner.locale,
            )
