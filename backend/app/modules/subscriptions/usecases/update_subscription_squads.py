from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.models import UpdateUserRequestDto

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SubscriptionDto, UpdateSubscriptionSquadsDto
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
            subscription = await self._subscription_repository.update_squads(data)
            await self._event_publisher.publish(
                SubscriptionEditedEvent(
                    user=actor, action="squads", subscription_id=data.subscription_id
                )
            )

        await self._remnawave_sdk.users.update_user(
            UpdateUserRequestDto(
                id=subscription.remnawave_user_id,
                active_internal_squads=subscription.internal_squads or None,
                external_squad_uuid=subscription.external_squad,
            )
        )

        logger.info(f"{actor.log} Updated squads for subscription '{data.subscription_id}'")
        return subscription
