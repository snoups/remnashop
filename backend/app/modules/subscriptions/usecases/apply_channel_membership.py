from typing import Optional

from loguru import logger
from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.settings import SettingsRepository
from app.modules.subscriptions.dto import ChannelMembershipDto, SubscriptionDto
from app.modules.subscriptions.eligibility import lock_live_subscription
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto, UserRepository


def _affected(subscription: SubscriptionDto, joined: bool) -> bool:
    if not subscription.is_trial:
        return False
    if joined:
        # an admin's own disable stays: only what a channel leave paused comes back
        return (
            subscription.status is SubscriptionStatus.DISABLED
            and subscription.paused_by_channel_leave
        )
    return subscription.status is SubscriptionStatus.ACTIVE


class ApplyChannelMembershipUseCase(UseCase[ChannelMembershipDto, Optional[UserDto]]):
    """Pauses a customer's trials when they leave the required channel and
    resumes them on return. Returns the customer when anything changed."""

    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        settings_repository: SettingsRepository,
        remnawave_sdk: RemnawaveSDK,
        lifecycle_service: SubscriptionLifecycleService,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._settings_repository = settings_repository
        self._remnawave_sdk = remnawave_sdk
        self._lifecycle_service = lifecycle_service
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: ChannelMembershipDto) -> Optional[UserDto]:
        async with self._uow:
            requirements = await self._settings_repository.get_bot_requirements()
            if not (
                requirements.trial_channel_guard
                and requirements.channel_required
                and requirements.channel_id == data.chat_id
            ):
                return None
            user = await self._user_repository.find_by_telegram_id(data.telegram_id)
            if user is None:
                return None
            owned = await self._subscription_repository.get_active_by_user(user.id)

        targets = [s for s in owned if _affected(s, data.joined)]
        users = self._remnawave_sdk.users
        for subscription in targets:
            if data.joined:
                panel_status = (await users.enable_user(subscription.remnawave_user_id)).status
            else:
                panel_status = (await users.disable_user(subscription.remnawave_user_id)).status
            async with self._uow:
                await lock_live_subscription(self._subscription_repository, subscription.id)
                await self._lifecycle_service.sync_status(
                    subscription.id, SubscriptionStatus(panel_status)
                )
                await self._subscription_repository.set_paused_by_channel_leave(
                    subscription.id, not data.joined
                )
                await self._event_publisher.publish(
                    SubscriptionEditedEvent(
                        actor=actor,
                        target=user,
                        action="enable" if data.joined else "disable",
                        subscription_id=subscription.id,
                    )
                )

        if not targets:
            return None
        verb = "Resumed" if data.joined else "Paused"
        logger.info(
            f"{actor.log} {verb} {len(targets)} trial(s) of {user.log} on channel membership"
        )
        return user
