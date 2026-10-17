from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.eligibility import get_manageable_subscription, subscription_owner
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.users import UserRepository


class DeleteSubscriptionUseCase(UseCase[int, None]):
    required_permission = Permission.SUBSCRIPTIONS_DELETE

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

    async def _execute(self, actor: Actor, data: int) -> None:
        async with self._uow:
            subscription = await get_manageable_subscription(
                self._subscription_repository, self._user_repository, actor, data
            )
            await self._revoker.revoke(subscription)
            subscriber = await subscription_owner(self._user_repository, subscription)
            await self._event_publisher.publish(
                SubscriptionEditedEvent(
                    actor=actor, target=subscriber, action="delete", subscription_id=data
                )
            )
        logger.info(f"{actor.log} Deleted subscription '{data}'")
