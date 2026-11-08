from decimal import Decimal

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.pricing import PricingRepository
from app.modules.transactions.dto import RateUnratedAnchorAmountsDto, UnratedAnchorCountDto
from app.modules.transactions.events import UnratedAnchorAmountsRatedEvent
from app.modules.transactions.repository import TransactionRepository


class RateUnratedAnchorAmountsUseCase(
    UseCase[RateUnratedAnchorAmountsDto, list[UnratedAnchorCountDto]]
):
    """Converts migrated amounts that kept their nominal value at today's rates."""

    required_permission = Permission.TRANSACTIONS_UNRATED_RATE

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(
        self, actor: Actor, data: RateUnratedAnchorAmountsDto
    ) -> list[UnratedAnchorCountDto]:
        async with self._uow:
            # an anchor switch rescales every amount: neither may run halfway through the other
            await self._pricing_repository.lock_settings()
            table = await self._pricing_repository.get_rate_table()
            counts = await self._transaction_repository.count_unrated_anchor_amounts()
            rated = [currency for currency in counts if currency in table.rows]
            for currency in rated:
                factor = table.convert(Decimal(1), currency, table.anchor)
                await self._transaction_repository.rate_unrated_anchor_amounts(currency, factor)
            if rated:
                await self._event_publisher.publish(
                    UnratedAnchorAmountsRatedEvent(
                        actor=actor,
                        currencies=sorted(rated),
                        count=sum(counts[currency] for currency in rated),
                        ip_address=data.client_ip,
                    )
                )
            remaining = await self._transaction_repository.count_unrated_anchor_amounts()
        logger.info(f"{actor.log} Rated migrated anchor amounts in {sorted(rated)}")
        return [
            UnratedAnchorCountDto(currency=currency, count=count)
            for currency, count in sorted(remaining.items())
        ]
