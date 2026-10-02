from typing import Optional

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.banners.dto import BannerDto, BannerKeyDto
from app.modules.banners.repository import BannerRepository


class GetBannerForDisplayUseCase(UseCase[BannerKeyDto, Optional[BannerDto]]):
    required_permission = Permission.PUBLIC

    def __init__(
        self, banner_repository: BannerRepository, config: AppConfig, uow: UnitOfWork
    ) -> None:
        self._banner_repository = banner_repository
        self._config = config
        self._uow = uow

    async def _execute(self, actor: Actor, data: BannerKeyDto) -> Optional[BannerDto]:
        async with self._uow:
            return await self._banner_repository.find_for_display(
                data.name, data.locale, self._config.default_locale
            )
