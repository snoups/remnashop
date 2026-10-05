from decimal import Decimal

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.loyalty.dto import RecalculateLoyaltyDto
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.tiers import months_before, resolve_percent
from app.modules.transactions import TransactionRepository
from app.modules.users import UserRepository


class RecalculateLoyaltyDiscountsUseCase(UseCase[RecalculateLoyaltyDto, int]):
    required_permission = None

    def __init__(
        self,
        loyalty_repository: LoyaltyRepository,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._loyalty_repository = loyalty_repository
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: RecalculateLoyaltyDto) -> int:
        async with self._uow:
            settings = await self._loyalty_repository.get_settings()
            active = settings.enabled and bool(settings.tiers)
            totals: dict[int, Decimal] = {}
            if active:
                paid_since = (
                    months_before(datetime_now(), settings.window_months)
                    if settings.window_months is not None
                    else None
                )
                totals = await self._transaction_repository.sum_paid_anchor_amount_per_user(
                    data.user_ids, paid_since=paid_since
                )
            if data.user_ids is not None:
                scope = data.user_ids
            else:
                discounted = await self._user_repository.list_user_ids_with_loyalty_discount()
                scope = sorted(set(totals) | set(discounted))

            changes: dict[int, int] = {}
            for state in await self._user_repository.list_loyalty_states(scope):
                target = 0
                if active and not state.excluded:
                    target = resolve_percent(totals.get(state.user_id, Decimal(0)), settings.tiers)
                if target != state.discount:
                    changes[state.user_id] = target
            await self._user_repository.set_loyalty_discounts(changes)
        logger.info(f"{actor.log} Recalculated loyalty discounts: {len(changes)} changed")
        return len(changes)
