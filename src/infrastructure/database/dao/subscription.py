from typing import Optional
from uuid import UUID

from adaptix import Retort
from adaptix.conversion import ConversionRetort
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.dao import SubscriptionDao
from src.application.dto import SubscriptionDto
from src.core.enums import SubscriptionStatus
from src.infrastructure.database.models import Subscription


class SubscriptionDaoImpl(SubscriptionDao):
    def __init__(
        self,
        session: AsyncSession,
        retort: Retort,
        conversion_retort: ConversionRetort,
        redis: Redis,
    ) -> None:
        self.session = session
        self.retort = retort
        self.conversion_retort = conversion_retort
        self.redis = redis

        self._convert_to_dto = self.conversion_retort.get_converter(Subscription, SubscriptionDto)
        self._convert_to_dto_list = self.conversion_retort.get_converter(
            list[Subscription], list[SubscriptionDto]
        )

    async def create(self, subscription: SubscriptionDto, telegram_id: int) -> SubscriptionDto:
        subscription_data = self.retort.dump(subscription)
        db_subscription = Subscription(**subscription_data, user_telegram_id=telegram_id)

        self.session.add(db_subscription)
        await self.session.flush()

        logger.debug(
            f"New subscription '{db_subscription.id}' created "
            f"for remna user '{subscription.user_remna_id}'"
        )
        return self._convert_to_dto(db_subscription)

    async def get_by_id(self, subscription_id: int) -> Optional[SubscriptionDto]:
        stmt = select(Subscription).where(Subscription.id == subscription_id)
        db_subscription = await self.session.scalar(stmt)

        if db_subscription:
            logger.debug(f"Subscription '{subscription_id}' found")
            return self._convert_to_dto(db_subscription)

        logger.debug(f"Subscription '{subscription_id}' not found")
        return None

    async def get_by_remna_id(self, user_remna_id: UUID) -> Optional[SubscriptionDto]:
        stmt = select(Subscription).where(Subscription.user_remna_id == user_remna_id)
        db_subscription = await self.session.scalar(stmt)

        if db_subscription:
            logger.debug(f"Subscription found by remna ID '{user_remna_id}'")
            return self._convert_to_dto(db_subscription)

        logger.debug(f"Subscription with remna ID '{user_remna_id}' not found")
        return None

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[SubscriptionDto]:
        stmt = (
            select(Subscription)
            .where(Subscription.user_telegram_id == telegram_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        db_subscription = await self.session.scalar(stmt)

        if db_subscription:
            logger.debug(f"Last subscription for telegram user '{telegram_id}' retrieved")
            return self._convert_to_dto(db_subscription)

        logger.debug(f"No subscriptions found for telegram user '{telegram_id}'")
        return None

    async def get_all_by_user(self, telegram_id: int) -> list[SubscriptionDto]:
        stmt = (
            select(Subscription)
            .where(Subscription.user_telegram_id == telegram_id)
            .order_by(Subscription.created_at.desc())
        )
        result = await self.session.scalars(stmt)
        db_subscriptions = list(result.all())

        logger.debug(f"Retrieved '{len(db_subscriptions)}' subscriptions for user '{telegram_id}'")
        return self._convert_to_dto_list(db_subscriptions)

    async def get_current(self, telegram_id: int) -> Optional[SubscriptionDto]:
        stmt = (
            select(Subscription)
            .where(Subscription.user_telegram_id == telegram_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        db_subscription = await self.session.scalar(stmt)

        if db_subscription:
            logger.debug(f"Current active subscription found for user '{telegram_id}'")
            return self._convert_to_dto(db_subscription)

        logger.debug(f"Active subscription not found for user '{telegram_id}'")
        return None

    async def update(self, subscription: SubscriptionDto) -> Optional[SubscriptionDto]:
        if not subscription.id:
            logger.warning("Subscription ID is missing, skipping update")
            return None

        if not subscription.changed_data:
            logger.debug(
                f"No changes detected for subscription '{subscription.id}', skipping update"
            )
            return await self.get_by_id(subscription.id)

        stmt = (
            update(Subscription)
            .where(Subscription.id == subscription.id)
            .values(**subscription.changed_data)
            .returning(Subscription)
        )
        db_subscription = await self.session.scalar(stmt)

        if db_subscription:
            logger.debug(
                f"Subscription '{subscription.id}' updated successfully "
                f"with data '{subscription.changed_data}'"
            )
            return self._convert_to_dto(db_subscription)

        logger.warning(f"Failed to update subscription '{subscription.id}'")
        return None

    async def update_status(
        self,
        subscription_id: int,
        status: SubscriptionStatus,
    ) -> Optional[SubscriptionDto]:
        stmt = (
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(status=status)
            .returning(Subscription)
        )
        db_subscription = await self.session.scalar(stmt)

        if db_subscription:
            logger.debug(f"Subscription '{subscription_id}' status updated to '{status}'")
            return self._convert_to_dto(db_subscription)

        logger.warning(f"Failed to update subscription '{subscription_id}': not found")
        return None

    async def exists(self, user_remna_id: UUID) -> bool:
        stmt = select(
            select(Subscription).where(Subscription.user_remna_id == user_remna_id).exists()
        )
        is_exists = await self.session.scalar(stmt) or False

        logger.debug(
            f"Subscription existence status for remna ID '{user_remna_id}' is '{is_exists}'"
        )
        return is_exists
