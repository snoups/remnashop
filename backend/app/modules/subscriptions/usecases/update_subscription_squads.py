from contextlib import suppress

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import UpdateUserRequestDto

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto, UpdateSubscriptionSquadsDto
from app.modules.subscriptions.eligibility import get_live_subscription
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.repository import SubscriptionRepository


class UpdateSubscriptionSquadsUseCase(UseCase[UpdateSubscriptionSquadsDto, SubscriptionDto]):
    required_permission = Permission.SUBSCRIPTIONS_SQUADS_MANAGE

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: UpdateSubscriptionSquadsDto) -> SubscriptionDto:
        async with self._uow:
            current = await get_live_subscription(
                self._subscription_repository, data.subscription_id
            )

        await self._remnawave_sdk.users.update_user(
            UpdateUserRequestDto(
                id=current.remnawave_user_id,
                active_internal_squads=data.internal_squads or None,
                external_squad_uuid=data.external_squad,
            )
        )

        async with self._uow:
            # deleted while the panel call was in flight
            locked = await self._subscription_repository.get_by_id_for_update(data.subscription_id)
            if locked.status is SubscriptionStatus.DELETED:
                # a plan change keeps the panel user for its new row; that row's squads win
                owner = await self._subscription_repository.get_by_remnawave_user_id_for_update(
                    current.remnawave_user_id
                )
            else:
                owner = None
                subscription = await self._subscription_repository.update_squads(data)
                await self._event_publisher.publish(
                    SubscriptionEditedEvent(
                        user=actor, action="squads", subscription_id=data.subscription_id
                    )
                )
        if locked.status is SubscriptionStatus.DELETED:
            restored = owner or current
            # best effort, outside the row lock: the edit lost its row, the panel user may not
            with suppress(Exception):
                await self._remnawave_sdk.users.update_user(
                    UpdateUserRequestDto(
                        id=current.remnawave_user_id,
                        active_internal_squads=restored.internal_squads or None,
                        external_squad_uuid=restored.external_squad,
                    )
                )
            raise ValidationError(
                f"Subscription '{data.subscription_id}' was deleted",
                code=ErrorCode.SUBSCRIPTION_DELETED,
            )

        logger.info(f"{actor.log} Updated squads for subscription '{data.subscription_id}'")
        return subscription
