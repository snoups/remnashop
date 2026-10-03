from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AttributedUserDto, ListAdLinkAttributedUsersDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UserRepository


class ListAdLinkAttributedUsersUseCase(
    UseCase[ListAdLinkAttributedUsersDto, tuple[list[AttributedUserDto], int]]
):
    required_permission = Permission.AD_LINKS_USERS_VIEW

    def __init__(
        self,
        ad_link_repository: AdLinkRepository,
        user_repository: UserRepository,
        transaction_repository: TransactionRepository,
        uow: UnitOfWork,
    ) -> None:
        self._ad_link_repository = ad_link_repository
        self._user_repository = user_repository
        self._transaction_repository = transaction_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListAdLinkAttributedUsersDto
    ) -> tuple[list[AttributedUserDto], int]:
        # NotFoundError (404) for an unknown ad_link_id, same as get_ad_link_stats
        async with self._uow:
            await self._ad_link_repository.get_by_id(data.ad_link_id)

            attributions, total = await self._ad_link_repository.list_attributions_paginated(
                data.ad_link_id, page=data.page, page_size=data.page_size
            )
            user_ids = [attribution.user_id for attribution in attributions]
            users_by_id = {
                user.id: user for user in await self._user_repository.list_by_ids(user_ids)
            }
            paid_user_ids = await self._transaction_repository.list_user_ids_with_paid_order(
                user_ids
            )

            result = [
                AttributedUserDto(
                    user_id=attribution.user_id,
                    name=users_by_id[attribution.user_id].name,
                    channel=attribution.channel,
                    created_at=attribution.created_at,
                    has_paid=attribution.user_id in paid_user_ids,
                )
                for attribution in attributions
                if attribution.user_id in users_by_id
            ]
            return result, total
