from datetime import timedelta

from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.transactions.dispatch import ProcessRecurringPaymentDispatch
from app.modules.transactions.recurring_repository import RecurringPaymentRepository


class EnqueueRecurringPaymentsUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        recurring_repository: RecurringPaymentRepository,
        dispatch: ProcessRecurringPaymentDispatch,
        uow: UnitOfWork,
        config: AppConfig,
    ) -> None:
        self._recurring = recurring_repository
        self._dispatch = dispatch
        self._uow = uow
        self._config = config

    async def _execute(self, actor: Actor, data: None) -> None:
        now = datetime_now()
        policy = self._config.recurring
        due_before = now + timedelta(minutes=max(1440, policy.notice_lead_minutes))
        lease = now + timedelta(minutes=policy.queue_lease_minutes)
        async with self._uow:
            debits = await self._recurring.list_due(
                now,
                due_before=due_before,
                limit=policy.batch_size,
                pending=False,
                claim_until=lease,
            )
            polls = await self._recurring.list_due(
                now,
                due_before=due_before,
                limit=policy.poll_batch_size,
                pending=True,
                claim_until=lease,
            )
        # Commit the leases before publishing. Each task receives its own request-scoped session;
        # a broker failure leaves a bounded lease for the next scheduler tick to reclaim.
        for subscription_id in (*debits, *polls):
            try:
                await self._dispatch.kiq(subscription_id=subscription_id)
            except Exception as error:
                logger.error(
                    f"Could not enqueue recurring subscription '{subscription_id}': "
                    f"{type(error).__name__}"
                )
