from typing import Optional

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import and_

from src.core.config import AppConfig
from src.core.enums import SubscriptionStatus
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.infrastructure.database.models.sql import Subscription, User
from src.infrastructure.redis import RedisRepository
from src.services.user import UserService

from .base import BaseService


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

        logger.info(
            f"Created subscription '{db_created_subscription.id}' for user '{user.telegram_id}'"
        )
        return SubscriptionDto.from_model(db_created_subscription)  # type: ignore[return-value]

    async def get(self, subscription_id: int) -> Optional[SubscriptionDto]:
        db_subscription = await self.uow.repository.subscriptions.get(subscription_id)

        if db_subscription:
            logger.debug(f"Retrieved subscription '{subscription_id}'")
        else:
            logger.warning(f"Subscription '{subscription_id}' not found")

        return SubscriptionDto.from_model(db_subscription)

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
            if subscription.user:
                await self.user_service.clear_user_cache(telegram_id=subscription.user.telegram_id)
            logger.info(f"Updated subscription '{subscription.id}' successfully")
        else:
            logger.warning(
                f"Attempted to update subscription '{subscription.id}', "
                "but subscription was not found or update failed"
            )

        return SubscriptionDto.from_model(db_updated_subscription)

    async def get_subscribed_users(self) -> list[UserDto]:
        db_users = await self.uow.repository.users._get_many(User)
        users = [user for user in db_users if user.current_subscription]
        logger.debug(f"Retrieved '{len(users)}' users with subscription")
        return UserDto.from_model_list(users)

    async def get_users_by_plan(self, plan_id: int) -> list[UserDto]:
        db_subscriptions = await self.uow.repository.subscriptions.filter_by_plan_id(plan_id)
        active_subs = [s for s in db_subscriptions if s.status == SubscriptionStatus.ACTIVE]

        if not active_subs:
            logger.debug(f"No active subscriptions found for plan '{plan_id}'")
            return []

        user_ids = [sub.user_telegram_id for sub in active_subs]
        db_users = await self.uow.repository.users.get_by_ids(telegram_ids=user_ids)
        users = UserDto.from_model_list(db_users)
        logger.debug(f"Retrieved '{len(users)}' users for active plan '{plan_id}'")
        return users

    async def get_unsubscribed_users(self) -> list[UserDto]:
        db_users = await self.uow.repository.users._get_many(User)
        users = [user for user in db_users if not user.current_subscription]
        logger.debug(f"Retrieved '{len(users)}' users without subscription")
        return UserDto.from_model_list(users)

    async def get_expired_users(self) -> list[UserDto]:
        db_users = await self.uow.repository.users._get_many(User)

        users = [
            user
            for user in db_users
            if user.current_subscription
            and user.current_subscription.status == SubscriptionStatus.EXPIRED
        ]

        logger.debug(f"Retrieved '{len(users)}' users with expired subscription")
        return UserDto.from_model_list(users)

    async def get_trial_users(self) -> list[UserDto]:
        db_users = await self.uow.repository.users._get_many(User)

        users = [
            user
            for user in db_users
            if user.current_subscription and user.current_subscription.is_trial
        ]

        logger.debug(f"Retrieved '{len(users)}' users with trial subscription")
        return UserDto.from_model_list(users)

    async def has_any_subscription(self, user: UserDto) -> bool:
        count = await self.uow.repository.subscriptions._count(
            Subscription, Subscription.user_telegram_id == user.telegram_id
        )
        return count > 0

    async def has_used_trial(self, user: UserDto) -> bool:
        conditions = and_(
            Subscription.user_telegram_id == user.telegram_id,
            Subscription.is_trial.is_(True),
            Subscription.status != SubscriptionStatus.DELETED,
        )

        count = await self.uow.repository.subscriptions._count(Subscription, conditions)
        return count > 0
