from typing import Final

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.analytics.dto import FunnelDto, FunnelStepDto, GetFunnelDto
from app.modules.analytics.window import resolve_since
from app.modules.subscriptions import SubscriptionRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UserRepository

_STEP_KEYS: Final[tuple[str, str, str, str]] = ("registered", "trial", "first_paid", "repeat_paid")


class GetFunnelUseCase(UseCase[GetFunnelDto, FunnelDto]):
    required_permission = Permission.ANALYTICS_FUNNEL_VIEW

    def __init__(
        self,
        user_repository: UserRepository,
        subscription_repository: SubscriptionRepository,
        transaction_repository: TransactionRepository,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository
        self._transaction_repository = transaction_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: GetFunnelDto) -> FunnelDto:
        since = await resolve_since(self._user_repository, data.days)
        async with self._uow:
            registered_ids = await self._user_repository.list_ids_registered_since(since, Role.USER)

            trial_ids = await self._subscription_repository.list_user_ids_with_trial(registered_ids)
            first_paid_ids = await self._transaction_repository.list_user_ids_with_paid_order(
                registered_ids
            )
            repeat_paid_ids = (
                await self._transaction_repository.list_user_ids_with_multiple_paid_orders(
                    registered_ids
                )
            )

            counts = [
                len(registered_ids),
                len(trial_ids),
                len(first_paid_ids),
                len(repeat_paid_ids),
            ]
            start = counts[0]
            steps = [
                FunnelStepDto(
                    key=_STEP_KEYS[i],
                    count=counts[i],
                    pct_of_start=(counts[i] / start) if start else 0.0,
                    pct_of_prev=(
                        1.0 if i == 0 else ((counts[i] / counts[i - 1]) if counts[i - 1] else 0.0)
                    ),
                )
                for i in range(len(_STEP_KEYS))
            ]
            return FunnelDto(days=data.days, steps=steps)
