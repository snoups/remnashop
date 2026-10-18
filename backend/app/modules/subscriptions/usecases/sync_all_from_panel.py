from typing import Final, Optional

from loguru import logger
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError
from remnapy.models import UserResponseDto

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PanelSyncDirection
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import PanelSyncResultDto
from app.modules.subscriptions.events import PanelSyncCompletedEvent
from app.modules.subscriptions.panel_sync import (
    differs_from_panel,
    finish_panel_sync,
    from_panel,
    panel_users,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.sync_subscription_status import (
    SyncSubscriptionStatusUseCase,
)

_SOURCE: Final[str] = "panel_sync"


class SyncAllFromPanelUseCase(UseCase[None, PanelSyncResultDto]):
    """Takes the panel's state into every live subscription that differs.

    One stream of the whole panel finds the candidates; each one is read again
    on its own before it is written, so a row changed while the stream ran is
    judged by the panel's current state, not the minutes-old snapshot.
    """

    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        sync_use_case: SyncSubscriptionStatusUseCase,
        uow: UnitOfWork,
        redis: Redis,
        event_publisher: EventPublisher,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._sync_use_case = sync_use_case
        self._uow = uow
        self._redis = redis
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: None) -> PanelSyncResultDto:
        async with self._uow:
            subscriptions = await self._subscription_repository.list_non_terminal()
        updated = failed = missing = 0
        try:
            snapshot = {user.id: user async for user in panel_users(self._remnawave_sdk)}
            for position, subscription in enumerate(subscriptions):
                listed = snapshot.get(subscription.remnawave_user_id)
                if listed is not None and not differs_from_panel(subscription, listed):
                    continue
                try:
                    fresh = await self._fresh(subscription.remnawave_user_id)
                except RemnawavePanelUnavailableError:
                    failed += len(subscriptions) - position
                    logger.warning(f"{actor.log} Panel sync from the panel stopped: panel down")
                    break
                except Exception:
                    logger.exception(f"Panel read failed for subscription '{subscription.id}'")
                    failed += 1
                    continue
                if fresh is not None and not differs_from_panel(subscription, fresh):
                    continue
                try:
                    await self._sync_use_case.system(
                        from_panel(fresh, subscription.remnawave_user_id, _SOURCE)
                    )
                except Exception:
                    logger.exception(f"Sync from the panel failed for '{subscription.id}'")
                    failed += 1
                    continue
                if fresh is None:
                    missing += 1
                else:
                    updated += 1
        except Exception:
            logger.exception(f"{actor.log} Panel sync from the panel failed")
            failed = len(subscriptions) - updated - missing
        result = PanelSyncResultDto(
            direction=PanelSyncDirection.FROM_PANEL,
            checked=len(subscriptions),
            updated=updated,
            failed=failed,
            missing=missing,
            finished_at=datetime_now(),
        )
        await finish_panel_sync(self._redis, PanelSyncDirection.FROM_PANEL, result)
        async with self._uow:
            await self._event_publisher.publish(
                PanelSyncCompletedEvent(
                    direction=result.direction.value,
                    checked=result.checked,
                    updated=result.updated,
                    failed=result.failed,
                    missing=result.missing,
                )
            )
        logger.info(f"{actor.log} Synced subscriptions from the panel: {result}")
        return result

    async def _fresh(self, remnawave_user_id: int) -> Optional[UserResponseDto]:
        try:
            return await self._remnawave_sdk.users.get_user_by_id(remnawave_user_id)
        except RemnawaveNotFoundError:
            return None
