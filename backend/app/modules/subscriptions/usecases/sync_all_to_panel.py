from loguru import logger
from redis.asyncio import Redis
from remnapy import RemnawaveSDK

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
    finish_panel_sync,
    panel_lags_behind,
    panel_users,
    push_to_panel,
)
from app.modules.subscriptions.repository import SubscriptionRepository


class SyncAllToPanelUseCase(UseCase[None, PanelSyncResultDto]):
    """Puts every live subscription's configuration into the panel where it differs."""

    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        uow: UnitOfWork,
        redis: Redis,
        event_publisher: EventPublisher,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
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
                user = snapshot.get(subscription.remnawave_user_id)
                if user is None:
                    missing += 1
                    continue
                if not panel_lags_behind(subscription, user):
                    continue
                try:
                    # the row as it is now, not as listed before the stream
                    async with self._uow:
                        current = await self._subscription_repository.get_by_id(subscription.id)
                    await push_to_panel(self._remnawave_sdk, current, user)
                except RemnawavePanelUnavailableError:
                    failed += len(subscriptions) - position
                    logger.warning(f"{actor.log} Panel sync to the panel stopped: panel down")
                    break
                except Exception:
                    logger.exception(
                        f"Push to the panel failed for subscription '{subscription.id}'"
                    )
                    failed += 1
                    continue
                updated += 1
        except Exception:
            logger.exception(f"{actor.log} Panel sync to the panel failed")
            failed = len(subscriptions) - updated - missing
        result = PanelSyncResultDto(
            direction=PanelSyncDirection.TO_PANEL,
            checked=len(subscriptions),
            updated=updated,
            failed=failed,
            missing=missing,
            finished_at=datetime_now(),
        )
        await finish_panel_sync(self._redis, PanelSyncDirection.TO_PANEL, result)
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
        logger.info(f"{actor.log} Synced subscriptions to the panel: {result}")
        return result
