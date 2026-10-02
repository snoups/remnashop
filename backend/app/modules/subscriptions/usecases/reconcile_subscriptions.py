from loguru import logger
from remnapy import RemnawaveSDK
from remnapy.exceptions import NotFoundError as RemnawaveNotFoundError

from app.core.actor import Actor
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
    ) -> None:
        self._subscription_repository = subscription_repository
        self._remnawave_sdk = remnawave_sdk
        self._sync_use_case = sync_use_case

    async def _execute(self, actor: Actor, data: None) -> None:
        # no batching, no concurrency limit -- list_non_terminal() loads
        # every non-terminal row into memory and each panel lookup runs
        # sequentially (the task's cron_lock only guards against overlapping the
        # *next* run, not this run's own latency). Fine at this project's current
        # scale; upgrade to paginated batches with a bounded gather() (or a panel
        # bulk-list endpoint) if this starts taking close to its 30-min interval.
        for subscription in await self._subscription_repository.list_non_terminal():
            try:
                panel_user = await self._remnawave_sdk.users.get_user_by_id(
                    subscription.remnawave_user_id
                )
            except RemnawaveNotFoundError:
                await self._sync_use_case.system(
                    SyncSubscriptionStatusDto(
                        remnawave_user_id=subscription.remnawave_user_id,
                        status=SubscriptionStatus.DELETED,
                        source="reconcile",
                    )
                )
                continue
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

            await self._sync_use_case.system(
                SyncSubscriptionStatusDto(
                    remnawave_user_id=subscription.remnawave_user_id,
                    status=SubscriptionStatus(panel_user.status),
                    source="reconcile",
                    expire_at=panel_user.expire_at,
                )
            )
