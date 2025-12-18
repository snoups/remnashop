from datetime import datetime, timedelta
from typing import Optional, TypeVar, Union

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from remnapy.enums.users import TrafficLimitStrategy
from sqlalchemy import and_

from src.core.config import AppConfig
from src.core.constants import TIME_1M, TIME_5M, TIME_10M, TIMEZONE
from src.core.enums import SubscriptionStatus
from src.core.storage.key_builder import build_key
from src.core.utils.time import datetime_now
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import (
    PlanDto,
    PlanSnapshotDto,
    RemnaSubscriptionDto,
    SubscriptionDto,
    UserDto,
)
from src.infrastructure.database.models.sql import Subscription
from src.infrastructure.redis import RedisRepository
from src.infrastructure.redis.cache import redis_cache
from src.services.user import UserService

from .base import BaseService

T = TypeVar("T", SubscriptionDto, RemnaSubscriptionDto)


class SubscriptionService(BaseService):
    uow: UnitOfWork
    user_service: UserService

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
        user_service: UserService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.user_service = user_service

    async def create(self, user: UserDto, subscription: SubscriptionDto) -> SubscriptionDto:
        data = subscription.model_dump(exclude={"user"})
        data["plan"] = subscription.plan.model_dump(mode="json")

        db_subscription = Subscription(**data, user_telegram_id=user.telegram_id)
        db_created_subscription = await self.uow.repository.subscriptions.create(db_subscription)

        await self.user_service.set_current_subscription(
            telegram_id=user.telegram_id,
            subscription_id=db_created_subscription.id,
        )
        await self.uow.commit()

        await self.clear_subscription_cache(db_subscription.id, db_subscription.user_telegram_id)
        logger.info(f"Created subscription '{db_subscription.id}' for user '{user.telegram_id}'")
        return SubscriptionDto.from_model(db_created_subscription)  # type: ignore[return-value]

    @redis_cache(prefix="get_subscription", ttl=TIME_5M)
    async def get(self, subscription_id: int) -> Optional[SubscriptionDto]:
        db_subscription = await self.uow.repository.subscriptions.get(subscription_id)

        if db_subscription:
            logger.debug(f"Retrieved subscription '{subscription_id}'")
        else:
            logger.warning(f"Subscription '{subscription_id}' not found")

        return SubscriptionDto.from_model(db_subscription)

    @redis_cache(prefix="get_current_subscription", ttl=TIME_1M)
    async def get_current(self, telegram_id: int) -> Optional[SubscriptionDto]:
        db_user = await self.uow.repository.users.get(telegram_id)

        if not db_user or not db_user.current_subscription_id:
            logger.debug(
                f"Current subscription check: User '{telegram_id}' has no active subscription"
            )
            return None

        subscription_id = db_user.current_subscription_id
        db_active_subscription = await self.uow.repository.subscriptions.get(subscription_id)

        if db_active_subscription:
            logger.debug(
                f"Current subscription check: Subscription '{subscription_id}' "
                f"retrieved for user '{telegram_id}'"
            )
        else:
            logger.warning(
                f"User '{telegram_id}' linked to subscription ID '{subscription_id}', "
                f"but subscription object was not found"
            )

        return SubscriptionDto.from_model(db_active_subscription)

    async def get_all_by_user(self, telegram_id: int) -> list[SubscriptionDto]:
        db_subscriptions = await self.uow.repository.subscriptions.get_all_by_user(telegram_id)
        logger.debug(f"Retrieved '{len(db_subscriptions)}' subscriptions for user '{telegram_id}'")
        return SubscriptionDto.from_model_list(db_subscriptions)

    async def get_all(self) -> list[SubscriptionDto]:
        db_subscriptions = await self.uow.repository.subscriptions.get_all()
        logger.debug(f"Retrieved '{len(db_subscriptions)}' total subscriptions")
        return SubscriptionDto.from_model_list(db_subscriptions)

    async def update(self, subscription: SubscriptionDto) -> Optional[SubscriptionDto]:
        data = subscription.changed_data.copy()

        if subscription.plan.changed_data or "plan" in data:
            data["plan"] = subscription.plan.model_dump(mode="json")

        db_updated_subscription = await self.uow.repository.subscriptions.update(
            subscription_id=subscription.id,  # type: ignore[arg-type]
            **data,
        )

        await self.uow.commit()

        if db_updated_subscription:
            await self.clear_subscription_cache(
                db_updated_subscription.id,
                db_updated_subscription.user_telegram_id,
            )
            await self.user_service.clear_user_cache(db_updated_subscription.user_telegram_id)
            logger.info(f"Updated subscription '{subscription.id}' successfully")
        else:
            logger.warning(
                f"Attempted to update subscription '{subscription.id}', "
                "but subscription was not found or update failed"
            )

        return SubscriptionDto.from_model(db_updated_subscription)

    @redis_cache(prefix="has_used_trial", ttl=TIME_10M)
    async def has_used_trial(self, user_telegram_id: int) -> bool:
        conditions = and_(
            Subscription.user_telegram_id == user_telegram_id,
            Subscription.is_trial.is_(True),
            Subscription.status != SubscriptionStatus.DELETED,
        )

        count = await self.uow.repository.subscriptions._count(Subscription, conditions)
        return count > 0

    async def clear_subscription_cache(self, subscription_id: int, user_telegram_id: int) -> None:
        list_cache_keys_to_invalidate = [
            build_key("cache", "get_subscription", subscription_id),
            build_key("cache", "get_current_subscription", user_telegram_id),
            build_key("cache", "has_used_trial", user_telegram_id),
        ]

        await self.redis_client.delete(*list_cache_keys_to_invalidate)
        logger.debug(f"Cache for subscription '{subscription_id}' invalidated")

    @staticmethod
    def subscriptions_match(
        bot_subscription: Optional[SubscriptionDto],
        remna_subscription: Optional[RemnaSubscriptionDto],
    ) -> bool:
        if not bot_subscription or not remna_subscription:
            return False

        return (
            bot_subscription.user_remna_id == remna_subscription.uuid
            and bot_subscription.status == remna_subscription.status
            and bot_subscription.url == remna_subscription.url
            and bot_subscription.traffic_limit == remna_subscription.traffic_limit
            and bot_subscription.device_limit == remna_subscription.device_limit
            and bot_subscription.expire_at == remna_subscription.expire_at
            and bot_subscription.external_squad == remna_subscription.external_squad
            and bot_subscription.traffic_limit_strategy == remna_subscription.traffic_limit_strategy
            and bot_subscription.tag == remna_subscription.tag
            and sorted(bot_subscription.internal_squads)
            == sorted(remna_subscription.internal_squads)
        )

    @staticmethod
    def plan_match(plan_a: PlanSnapshotDto, plan_b: PlanDto) -> bool:
        if not plan_a or not plan_b:
            return False

        return (
            plan_a.id == plan_b.id
            and plan_a.tag == plan_b.tag
            and plan_a.type == plan_b.type
            and plan_a.traffic_limit == plan_b.traffic_limit
            and plan_a.device_limit == plan_b.device_limit
            and plan_a.traffic_limit_strategy == plan_b.traffic_limit_strategy
            and sorted(plan_a.internal_squads) == sorted(plan_b.internal_squads)
            and plan_a.external_squad == plan_b.external_squad
        )

    @staticmethod
    def find_matching_plan(
        plan_snapshot: PlanSnapshotDto, plans: list[PlanDto]
    ) -> Optional[PlanDto]:
        return next(
            (plan for plan in plans if SubscriptionService.plan_match(plan_snapshot, plan)), None
        )

    @staticmethod
    def apply_sync(target: T, source: Union[SubscriptionDto, RemnaSubscriptionDto]) -> T:
        target_fields = set(type(target).model_fields)
        source_fields = set(type(source).model_fields)

        field_map = {"user_remna_id": "uuid"}

        for target_field, source_field in field_map.items():
            if target_field in target_fields and hasattr(source, source_field):
                old_value = getattr(target, target_field)
                new_value = getattr(source, source_field)
                if old_value != new_value:
                    logger.debug(
                        f"Field '{target_field}' changed from '{old_value}' to '{new_value}'"
                    )
                    setattr(target, target_field, new_value)

        common_fields = target_fields & source_fields

        for field in common_fields:
            old_value = getattr(target, field)
            new_value = getattr(source, field)
            if old_value != new_value:
                logger.debug(f"Field '{field}' changed from '{old_value}' to '{new_value}'")
                setattr(target, field, new_value)

        return target

    @staticmethod
    def get_traffic_reset_delta(strategy: TrafficLimitStrategy) -> Optional[timedelta]:
        now = datetime_now()

        if strategy == TrafficLimitStrategy.NO_RESET:
            return None

        if strategy == TrafficLimitStrategy.DAY:
            next_day = now.date() + timedelta(days=1)
            reset_at = datetime.combine(next_day, datetime.min.time(), tzinfo=TIMEZONE)
            return reset_at - now

        if strategy == TrafficLimitStrategy.WEEK:
            weekday = now.weekday()
            days_until = (7 - weekday) % 7 or 7
            date_target = now.date() + timedelta(days=days_until)
            reset_at = datetime(
                date_target.year, date_target.month, date_target.day, 0, 5, 0, tzinfo=TIMEZONE
            )
            return reset_at - now

        if strategy == TrafficLimitStrategy.MONTH:
            year = now.year
            month = now.month + 1
            if month == 13:
                year += 1
                month = 1
            reset_at = datetime(year, month, 1, 0, 10, 0, tzinfo=TIMEZONE)
            return reset_at - now

        raise ValueError("Unsupported strategy")
