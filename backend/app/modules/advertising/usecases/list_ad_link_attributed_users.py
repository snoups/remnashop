from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.advertising.dto import AttributedUserDto, ListAdLinkAttributedUsersDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.payments import PaymentOrderRepository
from app.modules.users import UserDto, UserRepository


class ListAdLinkAttributedUsersUseCase(
    UseCase[ListAdLinkAttributedUsersDto, tuple[list[AttributedUserDto], int]]
):
    required_permission = Permission.AD_LINKS_USERS_VIEW

    def __init__(
        self,
        ad_link_repository: AdLinkRepository,
        user_repository: UserRepository,
        payment_order_repository: PaymentOrderRepository,
    ) -> None:
        self._ad_link_repository = ad_link_repository
        self._user_repository = user_repository
        self._payment_order_repository = payment_order_repository

    async def _execute(
        self, actor: UserDto, data: ListAdLinkAttributedUsersDto
    ) -> tuple[list[AttributedUserDto], int]:
        # Raises NotFoundError for an unknown ad_link_id -- the router maps
        # that to 404, same as an unknown id would for get_ad_link_stats.
        await self._ad_link_repository.get_by_id(data.ad_link_id)

        attributions, total = await self._ad_link_repository.list_attributions_paginated(
            data.ad_link_id, page=data.page, page_size=data.page_size
        )
        user_ids = [attribution.user_id for attribution in attributions]
        users_by_id = {user.id: user for user in await self._user_repository.list_by_ids(user_ids)}
        paid_user_ids = await self._payment_order_repository.list_user_ids_with_paid_order(user_ids)

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
