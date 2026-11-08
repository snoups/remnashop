from typing import Final, Optional
from uuid import UUID

from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.events import changed_fields
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import (
    PushSubscriptionToPanelDto,
    SubscriptionDto,
    UpdateSubscriptionSquadsDto,
)
from app.modules.subscriptions.eligibility import get_manageable_subscription, subscription_owner
from app.modules.subscriptions.events import SubscriptionEditedEvent
from app.modules.subscriptions.panel_squads import replace_squads
from app.modules.subscriptions.panel_sync import push_to_panel, recreate_in_panel
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto, UserRepository

_SQUAD_FIELDS: Final[tuple[str, ...]] = ("internal_squads", "external_squad")


class PushSubscriptionToPanelUseCase(UseCase[PushSubscriptionToPanelDto, SubscriptionDto]):
    """Puts one subscription's configuration and on/off switch into the panel;
    a subscription whose panel user is gone gets a new one. Squads the panel
    no longer has are replaced first, as the admin picked."""

    required_permission = Permission.SUBSCRIPTIONS_PUSH_TO_PANEL

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        remnawave_sdk: RemnawaveSDK,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
        config: AppConfig,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._remnawave_sdk = remnawave_sdk
        self._event_publisher = event_publisher
        self._uow = uow
        self._prefix = config.remnawave.username_prefix

    async def _execute(self, actor: Actor, data: PushSubscriptionToPanelDto) -> SubscriptionDto:
        async with self._uow:
            subscription = await get_manageable_subscription(
                self._subscription_repository, self._user_repository, actor, data.subscription_id
            )
            owner = await subscription_owner(self._user_repository, subscription)
            subscription = await self._replace_squads(
                actor, owner, subscription, data.squad_replacements
            )
        try:
            await self._remnawave_sdk.users.get_user_by_id(subscription.remnawave_user_id)
        except RemnawaveNotFoundError:
            subscription = await recreate_in_panel(
                self._remnawave_sdk,
                self._subscription_repository,
                self._user_repository,
                self._uow,
                subscription,
                self._prefix,
            )
        else:
            await push_to_panel(self._remnawave_sdk, subscription, owner)

        async with self._uow:
            await self._event_publisher.publish(
                SubscriptionEditedEvent(
                    actor=actor,
                    target=owner,
                    action="push_to_panel",
                    subscription_id=subscription.id,
                )
            )
        logger.info(f"{actor.log} Pushed subscription '{subscription.id}' to the panel")
        return subscription

    async def _replace_squads(
        self,
        actor: Actor,
        owner: UserDto,
        subscription: SubscriptionDto,
        replacements: dict[UUID, Optional[UUID]],
    ) -> SubscriptionDto:
        internal, external = replace_squads(
            subscription.internal_squads, subscription.external_squad, replacements
        )
        if (internal, external) == (subscription.internal_squads, subscription.external_squad):
            return subscription
        updated = await self._subscription_repository.update_squads(
            UpdateSubscriptionSquadsDto(
                subscription_id=subscription.id, internal_squads=internal, external_squad=external
            )
        )
        await self._event_publisher.publish(
            SubscriptionEditedEvent(
                actor=actor,
                target=owner,
                action="squads",
                subscription_id=subscription.id,
                changed_fields=changed_fields(subscription, updated, _SQUAD_FIELDS),
            )
        )
        return updated
