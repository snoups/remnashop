from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.dto import BannerDto, BannerKeyDto
from app.modules.banners.repository import BannerRepository
from app.modules.translations import TranslationRepository


class GetBannerForDisplayUseCase(UseCase[BannerKeyDto, Optional[BannerDto]]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        banner_repository: BannerRepository,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
    ) -> None:
        self._banner_repository = banner_repository
        self._translation_repository = translation_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: BannerKeyDto) -> Optional[BannerDto]:
        async with self._uow:
            default_locale = await self._translation_repository.get_default_locale()
            return await self._banner_repository.find_for_display(
                data.name, data.locale, default_locale
            )
