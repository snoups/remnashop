from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AdLinkDto, ListAdLinksDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.users import UserDto


class ListAdLinksUseCase(UseCase[ListAdLinksDto, tuple[list[AdLinkDto], int]]):
    required_permission = Permission.AD_LINKS_VIEW

    def __init__(self, ad_link_repository: AdLinkRepository) -> None:
        self._ad_link_repository = ad_link_repository

    async def _execute(self, actor: UserDto, data: ListAdLinksDto) -> tuple[list[AdLinkDto], int]:
        return await self._ad_link_repository.list_paginated(
            is_active=data.is_active, page=data.page, page_size=data.page_size
        )
