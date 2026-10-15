from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import SyncSubscriptionStatusDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.sync_subscription_status import (
    SyncSubscriptionStatusUseCase,
)


class ReconcileSubscriptionsUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        remnawave_sdk: RemnawaveSDK,
        sync_use_case: SyncSubscriptionStatusUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._sync_use_case = sync_use_case
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> None:
        # No batching: every non-terminal row is loaded and checked against the
        # panel one by one. Fine at current scale; switch to paginated batches
        # with a bounded gather() if a run nears its 30-minute interval.
        async with self._uow:
            subscriptions = await self._subscription_repository.list_non_terminal()
        for subscription in subscriptions:
            try:
                panel_user = await self._remnawave_sdk.users.get_user_by_id(
                    subscription.remnawave_user_id
                )
            except RemnawaveNotFoundError:
                panel_user = None
            except RemnawavePanelUnavailableError:
                logger.warning(
                    "Reconcile sweep aborted: Remnawave panel circuit breaker is open; "
                    "remaining subscriptions will be picked up by the next scheduled sweep"
                )
                break
            except Exception:
                logger.exception(
                    f"Reconcile sweep failed for subscription '{subscription.id}' "
                    f"(remnawave_user_id={subscription.remnawave_user_id}); "
                    f"skipping, will retry next sweep"
                )
                continue

            if panel_user is None:
                sync = SyncSubscriptionStatusDto(
                    remnawave_user_id=subscription.remnawave_user_id,
                    status=SubscriptionStatus.DELETED,
                    source="reconcile",
                )
            else:
                sync = SyncSubscriptionStatusDto(
                    remnawave_user_id=subscription.remnawave_user_id,
                    status=SubscriptionStatus(panel_user.status),
                    source="reconcile",
                    expire_at=panel_user.expire_at,
                    first_connected_at=panel_user.first_connected_at,
                )
            try:
                await self._sync_use_case.system(sync)
            except Exception:
                # one bad row must not stop the sweep for every row after it
                logger.exception(
                    f"Reconcile sync failed for subscription '{subscription.id}'; "
                    f"will retry next sweep"
                )
