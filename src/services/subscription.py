from datetime import timedelta
from typing import Optional

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from remnawave import RemnawaveSDK
from remnawave.models import CreateUserRequestDto, UserResponseDto

from src.core.config import AppConfig
from src.core.utils.formatters import format_device_count, format_gb_to_bytes
from src.core.utils.time import datetime_now
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import PlanSnapshotDto, SubscriptionDto, UserDto
from src.infrastructure.redis import RedisRepository

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
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow
        self.remnawave = remnawave

    async def create(self, subscription: SubscriptionDto) -> SubscriptionDto:  # type: ignore
        pass

    async def get_by_user(self, telegram_id: int) -> Optional[SubscriptionDto]:
        db_subscription = await self.uow.repository.subscriptions.get_by_user(telegram_id)
        return SubscriptionDto.from_model(db_subscription)

    async def get_all(self) -> list[SubscriptionDto]:
        db_subscription = await self.uow.repository.subscriptions.get_all()
        return SubscriptionDto.from_model_list(db_subscription)

    async def update(self, subscription: SubscriptionDto) -> Optional[SubscriptionDto]:
        db_updated_subscription = await self.uow.repository.subscriptions.update(
            subscription_id=subscription.id,  # type: ignore[arg-type]
            **subscription.changed_data,
        )
        return SubscriptionDto.from_model(db_updated_subscription)

    #

    async def create_remnawave(self, user: UserDto, plan: PlanSnapshotDto) -> None:
        expire_at = datetime_now() + timedelta(days=plan.duration)
        # SubscriptionDto(expire_at=expire_at, plan=plan)

        created_user = await self.remnawave.users.create_user(
            CreateUserRequestDto(
                expire_at=expire_at,
                username=user.remna_name,
                traffic_limit_bytes=format_gb_to_bytes(plan.traffic_limit),
                # traffic_limit_strategy=,
                description=user.remna_description,
                # tag=,
                telegram_id=user.telegram_id,
                hwidDeviceLimit=format_device_count(plan.device_limit),
                active_internal_squads=[str(uid) for uid in plan.squad_ids],
            )
        )

        if not isinstance(created_user, UserResponseDto):
            logger.critical("")
            return

        # created_user.subscription_url
        logger.critical(created_user)
