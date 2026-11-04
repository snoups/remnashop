from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import ListSubscriptionsDto, SubscriptionListItemDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserRepository


class ListSubscriptionsUseCase(
    UseCase[ListSubscriptionsDto, tuple[list[SubscriptionListItemDto], int]]
):
    required_permission = Permission.SUBSCRIPTIONS_VIEW

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListSubscriptionsDto
    ) -> tuple[list[SubscriptionListItemDto], int]:
        async with self._uow:
            subscriptions, total = await self._subscription_repository.list_paginated(
                status=data.status,
                search=data.search,
                user_id=data.user_id,
                page=data.page,
                page_size=data.page_size,
                hide_staff_from=None
                if PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
                else actor.id,
            )
            owners = await self._user_repository.get_many_by_ids(
                [subscription.user_id for subscription in subscriptions]
            )
        names = {owner.id: owner.name for owner in owners if owner.deleted_at is None}
        return [
            SubscriptionListItemDto(
                subscription=subscription, user_name=names.get(subscription.user_id)
            )
            for subscription in subscriptions
        ], total
