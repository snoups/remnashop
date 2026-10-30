from typing import Optional

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import UpdateUserRequestDto

from app.core.actor import Actor
from app.core.constants import GB_TO_BYTES
from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, SubscriptionStatus
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.plans import AddOnRepository
from app.modules.subscriptions.dto import GrantAddOnDto, SubscriptionDto
from app.modules.subscriptions.events import SubscriptionAddOnGrantedEvent
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserRepository


class GrantAddOnUseCase(UseCase[GrantAddOnDto, SubscriptionDto]):
    # system-only: grant_addon_task runs it for a promocode's TRAFFIC/DEVICES
    # reward
    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        addon_repository: AddOnRepository,
        user_repository: UserRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._addon_repository = addon_repository
        self._user_repository = user_repository
        self._remnawave_sdk = remnawave_sdk
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: GrantAddOnDto) -> SubscriptionDto:
        async with self._uow:
            addon = await self._addon_repository.get_by_id(data.addon_id)
            target = await self._lock_live_target(data.subscription_id)
            if target is None:
                logger.warning(
                    f"Addon '{addon.id}' not granted: subscription '{data.subscription_id}' "
                    f"and its panel user are gone"
                )
                return await self._subscription_repository.get_by_id(data.subscription_id)

            subscription = await self._subscription_repository.grant_entitlement(
                subscription_id=target.id,
                addon_id=addon.id,
                addon_type=addon.type,
                amount=addon.amount,
                idempotency_key=data.idempotency_key,
            )
            # pushed under the row lock: a plan change locks this row before it
            # commits, so it sees the grant and configures the panel after it
            if addon.type == AddOnType.TRAFFIC:
                request = UpdateUserRequestDto(
                    id=subscription.remnawave_user_id,
                    traffic_limit_bytes=subscription.effective_traffic_limit * GB_TO_BYTES,
                )
            else:
                request = UpdateUserRequestDto(
                    id=subscription.remnawave_user_id,
                    hwid_device_limit=subscription.effective_device_limit,
                )
            await self._remnawave_sdk.users.update_user(request)

        logger.info(
            f"Granted addon '{addon.id}' ({addon.amount} {addon.type.value}) "
            f"to subscription '{subscription.id}'"
        )
        # retry-safe: only update_user above raises a retried exception, so a
        # failed attempt never gets here and the event fires once
        async with self._uow:
            recipient = await self._user_repository.find_by_id(subscription.user_id)
            await self._event_publisher.publish(
                SubscriptionAddOnGrantedEvent(
                    user=actor,
                    target=recipient,
                    subscription_id=subscription.id,
                    addon_id=addon.id,
                    addon_type=addon.type,
                    amount=addon.amount,
                )
            )
        return subscription

    async def _lock_live_target(self, subscription_id: int) -> Optional[SubscriptionDto]:
        target = await self._subscription_repository.get_by_id_for_update(subscription_id)
        if target.status is not SubscriptionStatus.DELETED:
            return target
        # replaced by a plan change after the promocode was activated: the reward
        # goes to the row that owns the panel user now
        live = await self._subscription_repository.find_by_remnawave_user_id_for_update(
            target.remnawave_user_id
        )
        if live is None or live.status is SubscriptionStatus.DELETED:
            return None
        return live
