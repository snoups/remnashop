from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AdLinkDto, ListAdLinksDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.users import UserDto


class ListAdLinksUseCase(UseCase[ListAdLinksDto, tuple[list[AdLinkDto], int]]):
    required_permission = Permission.AD_LINKS_VIEW

    def __init__(self, ad_link_repository: AdLinkRepository, uow: UnitOfWork) -> None:
        self._ad_link_repository = ad_link_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: ListAdLinksDto) -> tuple[list[AdLinkDto], int]:
        async with self._uow:
            return await self._ad_link_repository.list_paginated(
                is_active=data.is_active, page=data.page, page_size=data.page_size
            )
