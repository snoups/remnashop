from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AdLinkDto, CreateAdLinkDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.users import UserDto


class CreateAdLinkUseCase(UseCase[CreateAdLinkDto, AdLinkDto]):
    required_permission = Permission.AD_LINKS_CREATE

    def __init__(self, ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: CreateAdLinkDto) -> AdLinkDto:
        async with self._uow:
            ad_link = await self._ad_link_repository.create(data)
        logger.info(f"{actor.log} Created ad link '{ad_link.code}'")
        return ad_link
