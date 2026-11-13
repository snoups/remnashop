from contextlib import suppress

from loguru import logger
from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SetSubscriptionEnabledDto, SubscriptionDto
from app.modules.subscriptions.eligibility import (
    get_manageable_subscription,
    lock_live_subscription,
    subscription_owner,
)
from app.modules.subscriptions.events import SubscriptionEditAction, SubscriptionEditedEvent
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserRepository


class SetSubscriptionEnabledUseCase(UseCase[SetSubscriptionEnabledDto, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_STATUS_MANAGE

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        remnawave_sdk: RemnawaveSDK,
        lifecycle_service: SubscriptionLifecycleService,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._remnawave_sdk = remnawave_sdk
        self._lifecycle_service = lifecycle_service
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: SetSubscriptionEnabledDto) -> SubscriptionDto:
        async with self._uow:
            subscription = await get_manageable_subscription(
                self._subscription_repository, self._user_repository, actor, data.subscription_id
            )

        users = self._remnawave_sdk.users
        if data.enabled:
            panel_status = (await users.enable_user(subscription.remnawave_user_id)).status
        else:
            panel_status = (await users.disable_user(subscription.remnawave_user_id)).status

        action: SubscriptionEditAction = "enable" if data.enabled else "disable"
        try:
            async with self._uow:
                await lock_live_subscription(self._subscription_repository, subscription.id)
                updated = await self._lifecycle_service.sync_status(
                    subscription.id, SubscriptionStatus(panel_status)
                )
                # an admin's choice: a later channel rejoin must not undo it
                await self._subscription_repository.set_paused_by_channel_leave(
                    subscription.id, False
                )
                subscriber = await subscription_owner(self._user_repository, subscription)
                await self._event_publisher.publish(
                    SubscriptionEditedEvent(
                        actor=actor,
                        target=subscriber,
                        action=action,
                        subscription_id=subscription.id,
                    )
                )
        except Exception:
            with suppress(Exception):
                await self._undo_toggle(subscription, enabled=data.enabled)
            raise

        logger.info(f"{actor.log} Set subscription '{subscription.id}' {action}d")
        return updated

    async def _undo_toggle(self, subscription: SubscriptionDto, *, enabled: bool) -> None:
        # a plan change keeps the panel user for its new row; only that row's state counts
        async with self._uow:
            owner = await self._subscription_repository.find_by_remnawave_user_id_for_update(
                subscription.remnawave_user_id
            )
        if owner is None or owner.status is SubscriptionStatus.DELETED:
            return
        if enabled and owner.status is SubscriptionStatus.DISABLED:
            await self._remnawave_sdk.users.disable_user(owner.remnawave_user_id)
        elif not enabled and owner.status is not SubscriptionStatus.DISABLED:
            await self._remnawave_sdk.users.enable_user(owner.remnawave_user_id)
