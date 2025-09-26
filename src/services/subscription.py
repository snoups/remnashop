from typing import Optional

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis
from remnawave import RemnawaveSDK

from src.core.config import AppConfig
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import SubscriptionDto, UserDto
from src.infrastructure.database.models.sql import Subscription
from src.infrastructure.redis import RedisRepository
from src.services.user import UserService

from .base import BaseService


class SubscriptionService(BaseService):
    uow: UnitOfWork

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
        remnawave: RemnawaveSDK,
        user_service: UserService,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.remnawave = remnawave
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
        return SubscriptionDto.from_model(db_created_subscription)  # type: ignore[return-value]

    async def get_current(self, telegram_id: int) -> Optional[SubscriptionDto]:
        db_user = await self.uow.repository.users.get(telegram_id)

        if not db_user or not db_user.current_subscription:
            return None

        subscription_id = db_user.current_subscription.id
        db_active_subscription = await self.uow.repository.subscriptions.get(subscription_id)

        return SubscriptionDto.from_model(db_active_subscription)

    async def get_all_by_user(self, telegram_id: int) -> list[SubscriptionDto]:
        db_subscriptions = await self.uow.repository.subscriptions.get_all_by_user(telegram_id)
        return SubscriptionDto.from_model_list(db_subscriptions)

    async def get_all(self) -> list[SubscriptionDto]:
        db_subscription = await self.uow.repository.subscriptions.get_all()
        return SubscriptionDto.from_model_list(db_subscription)

    async def update(self, subscription: SubscriptionDto) -> Optional[SubscriptionDto]:
        db_updated_subscription = await self.uow.repository.subscriptions.update(
            subscription_id=subscription.id,  # type: ignore[arg-type]
            **subscription.changed_data,
        )
        return SubscriptionDto.from_model(db_updated_subscription)
