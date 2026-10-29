from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import DeletedSubscriptionsDto
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.users import UserRepository, assert_manageable, get_visible_target


class DeleteUserSubscriptionsUseCase(UseCase[int, DeletedSubscriptionsDto]):
    """Deletes every live subscription of a user, its panel user too."""

    required_permission = Permission.SUBSCRIPTIONS_DELETE_ALL

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        revoker: PanelSubscriptionRevoker,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._revoker = revoker
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> DeletedSubscriptionsDto:
        async with self._uow:
            target = await get_visible_target(self._user_repository, actor, data)
            assert_manageable(actor, target)
            subscriptions = await self._subscription_repository.get_live_by_user(target.id)

        deleted = 0
        # one transaction each: a panel failure halfway keeps what's already deleted
        for subscription in subscriptions:
            async with self._uow:
                locked = await self._subscription_repository.get_by_id_for_update(subscription.id)
                if locked.status is SubscriptionStatus.DELETED:
                    continue
                await self._revoker.revoke(locked)
                await self._event_publisher.publish(
                    SubscriptionEditedEvent(
                        actor=actor, target=target, action="delete", subscription_id=locked.id
                    )
                )
            deleted += 1

        logger.info(f"{actor.log} Deleted {deleted} subscription(s) of user '{target.id}'")
        return DeletedSubscriptionsDto(deleted=deleted)
