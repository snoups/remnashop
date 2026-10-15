from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.pricing.dto import CurrencyRateDto, UpdateCurrencyRateDto
from app.modules.pricing.events import CurrencyRateChangedEvent
from app.modules.pricing.repository import PricingRepository


class UpdateCurrencyRateUseCase(UseCase[UpdateCurrencyRateDto, list[CurrencyRateDto]]):
    required_permission = Permission.PRICING_RATES_MANAGE

    def __init__(
        self,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateCurrencyRateDto) -> list[CurrencyRateDto]:
        async with self._uow:
            # under the same lock update_rate takes, so the audited old rate is the replaced one
            await self._pricing_repository.lock_settings()
            old_row = (await self._pricing_repository.get_rate_table()).for_currency(data.currency)
            await self._pricing_repository.update_rate(data)
            await self._event_publisher.publish(
                CurrencyRateChangedEvent(
                    actor=actor,
                    currency=data.currency,
                    old_rate=str(old_row.rate),
                    new_rate=str(data.rate),
                )
            )
            table = await self._pricing_repository.get_rate_table()
        logger.info(f"{actor.log} Updated currency rate for '{data.currency}'")
        return list(table.rows.values())
