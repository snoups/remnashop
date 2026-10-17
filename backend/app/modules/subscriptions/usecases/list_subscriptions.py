from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import ListSubscriptionsDto, SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository


class ListSubscriptionsUseCase(UseCase[ListSubscriptionsDto, tuple[list[SubscriptionDto], int]]):
    required_permission = Permission.SUBSCRIPTIONS_VIEW

    def __init__(self, subscription_repository: SubscriptionRepository, uow: UnitOfWork) -> None:
        self._subscription_repository = subscription_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListSubscriptionsDto
    ) -> tuple[list[SubscriptionDto], int]:
        async with self._uow:
            return await self._subscription_repository.list_paginated(
                status=data.status,
                search=data.search,
                user_id=data.user_id,
                page=data.page,
                page_size=data.page_size,
                hide_staff_from=None
                if PermissionPolicy.has_permission(actor, Permission.ADMINS_MANAGE)
                else actor.id,
            )
