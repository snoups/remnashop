from typing import Final, Optional

from loguru import logger
from redis.asyncio import Redis
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError
from remnapy.models import UserResponseDto

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import PanelSyncDirection, SubscriptionStatus
from app.core.exceptions import RemnawavePanelUnavailableError, ValidationError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.plans import PlanRepository
from app.modules.subscriptions.dto import PanelSyncResultDto, SyncFromPanelOptionsDto
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.subscriptions.events import PanelSyncCompletedEvent, StatusSyncSource
from app.modules.subscriptions.panel_sync import (
    differs_from_panel,
    finish_panel_sync,
    from_panel,
    holding_panel_sync,
    imported_row,
    is_orphan,
    match_shop_user,
    named_shop_user,
    panel_users,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.sync_subscription_status import (
    SyncSubscriptionStatusUseCase,
)
from app.modules.users import UserRepository

_SOURCE: Final[StatusSyncSource] = "panel_sync"


class SyncAllFromPanelUseCase(UseCase[SyncFromPanelOptionsDto, PanelSyncResultDto]):
    """Takes the panel's state into every live subscription that differs.

    One stream of the whole panel finds the candidates; each one is read again
    on its own before it is written, so a row changed while the stream ran is
    judged by the panel's current state, not the minutes-old snapshot.
    A shop user's panel user that no subscription stands for is imported;
    one the shop didn't name only with `adopt_unnamed`, and none past the
    owner's subscription cap with `respect_subscription_limit`.
    """

    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        plan_repository: PlanRepository,
        remnawave_sdk: RemnawaveSDK,
        sync_use_case: SyncSubscriptionStatusUseCase,
        uow: UnitOfWork,
        redis: Redis,
        event_publisher: EventPublisher,
        eligibility: PurchaseEligibility,
        config: AppConfig,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._user_repository = user_repository
        self._plan_repository = plan_repository
        self._remnawave_sdk = remnawave_sdk
        self._sync_use_case = sync_use_case
        self._uow = uow
        self._redis = redis
        self._event_publisher = event_publisher
        self._eligibility = eligibility
        self._prefix = config.remnawave.username_prefix

    async def _execute(self, actor: Actor, data: SyncFromPanelOptionsDto) -> PanelSyncResultDto:
        async with holding_panel_sync(self._redis, PanelSyncDirection.FROM_PANEL):
            return await self._sync(actor, data)

    async def _sync(self, actor: Actor, options: SyncFromPanelOptionsDto) -> PanelSyncResultDto:
        async with self._uow:
            subscriptions = await self._subscription_repository.list_non_terminal()
            linked = await self._subscription_repository.list_linked_remnawave_user_ids()
        updated = failed = missing = imported = over_limit = 0
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
            else:
                imported, over_limit, import_failed = await self._import_orphans(
                    actor, snapshot, linked, options
                )
                failed += import_failed
        except Exception:
            logger.exception(f"{actor.log} Panel sync from the panel failed")
            failed = len(subscriptions) - updated - missing
        result = PanelSyncResultDto(
            direction=PanelSyncDirection.FROM_PANEL,
            checked=len(subscriptions),
            updated=updated,
            failed=failed,
            missing=missing,
            imported=imported,
            over_limit=over_limit,
            finished_at=datetime_now(),
        )
        await finish_panel_sync(self._redis, PanelSyncDirection.FROM_PANEL, result)
        async with self._uow:
            await self._event_publisher.publish(
                PanelSyncCompletedEvent(
                    direction=result.direction,
                    checked=result.checked,
                    updated=result.updated,
                    failed=result.failed,
                    missing=result.missing,
                    imported=result.imported,
                )
            )
        logger.info(f"{actor.log} Synced subscriptions from the panel: {result}")
        return result

    async def _import_orphans(
        self,
        actor: Actor,
        snapshot: dict[int, UserResponseDto],
        linked: set[int],
        options: SyncFromPanelOptionsDto,
    ) -> tuple[int, int, int]:
        """(imported, over_limit, failed) for the panel users no subscription stands for."""
        now = datetime_now()
        orphans = [user for user in snapshot.values() if is_orphan(user, linked, now)]
        if not orphans:
            return 0, 0, 0
        async with self._uow:
            plans = await self._plan_repository.list_all()
        imported = over_limit = failed = 0
        for user in orphans:
            try:
                async with self._uow:
                    owner = (
                        await match_shop_user(self._user_repository, user, self._prefix)
                        if options.adopt_unnamed
                        else await named_shop_user(
                            self._user_repository, user.username, self._prefix
                        )
                    )
                    if owner is None or owner.deleted_at is not None:
                        continue
                    # linked while the sync ran
                    existing = await self._subscription_repository.find_by_remnawave_user_id(
                        user.id
                    )
                    if existing is not None and existing.status is not SubscriptionStatus.DELETED:
                        continue
                    if options.respect_subscription_limit:
                        try:
                            await self._eligibility.assert_below_cap(owner.id)
                        except ValidationError:
                            over_limit += 1
                            logger.info(
                                f"{actor.log} Skipped panel user {user.id}: "
                                f"user '{owner.id}' is at the subscription cap"
                            )
                            continue
                    created = await self._subscription_repository.create(
                        imported_row(user, owner, plans)
                    )
            except Exception:
                logger.exception(f"Import of panel user {user.id} failed")
                failed += 1
                continue
            imported += 1
            logger.info(
                f"{actor.log} Imported panel user {user.id} "
                f"as subscription '{created.id}' of user '{owner.id}'"
            )
        return imported, over_limit, failed

    async def _fresh(self, remnawave_user_id: int) -> Optional[UserResponseDto]:
        try:
            return await self._remnawave_sdk.users.get_user_by_id(remnawave_user_id)
        except RemnawaveNotFoundError:
            return None
