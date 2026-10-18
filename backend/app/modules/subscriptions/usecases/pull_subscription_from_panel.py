from typing import Final, Optional

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError
from remnapy.models import UserResponseDto

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.eligibility import get_manageable_subscription, subscription_owner
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.panel_sync import from_panel
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.sync_subscription_status import (
    SyncSubscriptionStatusUseCase,
)
from app.modules.users import UserRepository

_SOURCE: Final[str] = "admin_pull"


class PullSubscriptionFromPanelUseCase(UseCase[int, SubscriptionDto]):
    """Takes the panel's state into one subscription; gone from the panel, it
    is marked deleted."""

    required_permission = Permission.SUBSCRIPTIONS_PULL_FROM_PANEL

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        remnawave_sdk: RemnawaveSDK,
        sync_use_case: SyncSubscriptionStatusUseCase,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._remnawave_sdk = remnawave_sdk
        self._sync_use_case = sync_use_case
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> SubscriptionDto:
        async with self._uow:
            subscription = await get_manageable_subscription(
                self._subscription_repository, self._user_repository, actor, data
            )
        user: Optional[UserResponseDto]
        try:
            user = await self._remnawave_sdk.users.get_user_by_id(subscription.remnawave_user_id)
        except RemnawaveNotFoundError:
            user = None
        await self._sync_use_case.system(from_panel(user, subscription.remnawave_user_id, _SOURCE))

        async with self._uow:
            synced = await self._subscription_repository.get_by_id(subscription.id)
            await self._event_publisher.publish(
                SubscriptionEditedEvent(
                    actor=actor,
                    target=await subscription_owner(self._user_repository, subscription),
                    action="pull_from_panel",
                    subscription_id=subscription.id,
                )
            )
        logger.info(f"{actor.log} Pulled subscription '{subscription.id}' from the panel")
        return synced
