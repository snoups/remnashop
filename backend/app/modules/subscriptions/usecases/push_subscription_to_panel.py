from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto
from app.modules.subscriptions.eligibility import get_manageable_subscription, subscription_owner
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.panel_sync import push_to_panel
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserRepository


class PushSubscriptionToPanelUseCase(UseCase[int, SubscriptionDto]):
    """Puts one subscription's configuration and on/off switch into the panel."""

    required_permission = Permission.SUBSCRIPTIONS_PUSH_TO_PANEL

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        remnawave_sdk: RemnawaveSDK,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._remnawave_sdk = remnawave_sdk
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> SubscriptionDto:
        async with self._uow:
            subscription = await get_manageable_subscription(
                self._subscription_repository, self._user_repository, actor, data
            )
        try:
            user = await self._remnawave_sdk.users.get_user_by_id(subscription.remnawave_user_id)
        except RemnawaveNotFoundError as error:
            raise ConflictError(
                "The panel has no user for this subscription",
                code=ErrorCode.SUBSCRIPTION_PANEL_USER_MISSING,
            ) from error
        await push_to_panel(self._remnawave_sdk, subscription, user)

        async with self._uow:
            await self._event_publisher.publish(
                SubscriptionEditedEvent(
                    actor=actor,
                    target=await subscription_owner(self._user_repository, subscription),
                    action="push_to_panel",
                    subscription_id=subscription.id,
                )
            )
        logger.info(f"{actor.log} Pushed subscription '{subscription.id}' to the panel")
        return subscription
