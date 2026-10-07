from contextlib import suppress
from typing import Optional

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import UpdateUserRequestDto

from app.core.actor import Actor
from app.core.constants import GB_TO_BYTES
from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, SubscriptionStatus
from app.core.events import set_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto, UpdateSubscriptionDto
from app.modules.subscriptions.eligibility import get_live_subscription
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.purchase_subscription.panel import restore


def _effective(base: int, subscription: SubscriptionDto, addon_type: AddOnType) -> int:
    # 0 = unlimited; an add-on on top must not turn it into a finite cap
    bonus = sum(e.amount for e in subscription.addon_entitlements if e.type is addon_type)
    return base and base + bonus


class UpdateSubscriptionUseCase(UseCase[UpdateSubscriptionDto, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_UPDATE

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
        lifecycle_service: SubscriptionLifecycleService,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._event_publisher = event_publisher
        self._uow = uow
        self._lifecycle_service = lifecycle_service

    async def _execute(self, actor: Actor, data: UpdateSubscriptionDto) -> SubscriptionDto:
        async with self._uow:
            old = await get_live_subscription(self._subscription_repository, data.subscription_id)

        panel_status: Optional[SubscriptionStatus] = None
        touches_panel = any(
            value is not None
            for value in (
                data.traffic_limit,
                data.device_limit,
                data.traffic_limit_strategy,
                data.expire_at,
            )
        )
        if touches_panel:
            traffic_limit = old.traffic_limit if data.traffic_limit is None else data.traffic_limit
            device_limit = old.device_limit if data.device_limit is None else data.device_limit
            panel_user = await self._remnawave_sdk.users.update_user(
                UpdateUserRequestDto(
                    id=old.remnawave_user_id,
                    traffic_limit_bytes=_effective(traffic_limit, old, AddOnType.TRAFFIC)
                    * GB_TO_BYTES,
                    hwid_device_limit=_effective(device_limit, old, AddOnType.DEVICES),
                    traffic_limit_strategy=data.traffic_limit_strategy,
                    expire_at=data.expire_at,
                )
            )
            panel_status = SubscriptionStatus(panel_user.status)

        try:
            async with self._uow:
                subscription = await self._subscription_repository.update(data)
                if panel_status is not None:
                    subscription = await self._lifecycle_service.sync_status(
                        subscription.id, panel_status
                    )
                await self._event_publisher.publish(
                    SubscriptionEditedEvent(
                        user=actor,
                        action="update",
                        subscription_id=data.subscription_id,
                        changed_fields=set_fields(data, skip=frozenset({"subscription_id"})),
                    )
                )
        except Exception:
            if touches_panel:
                with suppress(Exception):
                    await self._remnawave_sdk.users.update_user(restore(old))
            raise

        logger.info(f"{actor.log} Updated subscription '{subscription.id}'")
        return subscription
