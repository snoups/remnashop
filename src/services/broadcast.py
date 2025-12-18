from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import and_

from src.core.config import AppConfig
from src.core.enums import (
    BroadcastAudience,
    BroadcastStatus,
    PlanAvailability,
    SubscriptionStatus,
)
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import BroadcastDto, BroadcastMessageDto, UserDto
from src.infrastructure.database.models.sql import Broadcast, BroadcastMessage, Subscription, User
from src.infrastructure.database.models.sql.plan import Plan
from src.infrastructure.redis import RedisRepository

from .base import BaseService


class BroadcastService(BaseService):
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
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow

    async def create(self, broadcast: BroadcastDto) -> BroadcastDto:
        db_broadcast = Broadcast(**broadcast.model_dump())
        db_created_broadcast = await self.uow.repository.broadcasts.create(db_broadcast)
        await self.uow.commit()
        logger.info(f"Created broadcast '{broadcast.task_id}'")
        return BroadcastDto.from_model(db_created_broadcast)  # type: ignore[return-value]

    async def create_messages(
        self,
        broadcast_id: int,
        messages: list[BroadcastMessageDto],
    ) -> list[BroadcastMessageDto]:
        db_messages = [
            BroadcastMessage(
                broadcast_id=broadcast_id,
                user_id=m.user_id,
                status=m.status,
            )
            for m in messages
        ]
        db_created_messages = await self.uow.repository.broadcasts.create_messages(db_messages)
        return BroadcastMessageDto.from_model_list(db_created_messages)

    async def get(self, task_id: UUID) -> Optional[BroadcastDto]:
        db_broadcast = await self.uow.repository.broadcasts.get(task_id)

        if db_broadcast:
            logger.debug(f"Retrieved broadcast '{task_id}'")
        else:
            logger.warning(f"Broadcast '{task_id}' not found")

        return BroadcastDto.from_model(db_broadcast)

    async def get_all(self) -> list[BroadcastDto]:
        db_broadcasts = await self.uow.repository.broadcasts.get_all()
        return BroadcastDto.from_model_list(list(reversed(db_broadcasts)))

    async def update(self, broadcast: BroadcastDto) -> Optional[BroadcastDto]:
        db_updated_broadcast = await self.uow.repository.broadcasts.update(
            task_id=broadcast.task_id,
            **broadcast.changed_data,
        )

        if db_updated_broadcast:
            logger.info(f"Updated broadcast '{broadcast.task_id}' successfully")
        else:
            logger.warning(
                f"Attempted to update broadcast '{broadcast.task_id}', "
                f"but broadcast was not found or update failed"
            )

        return BroadcastDto.from_model(db_updated_broadcast)

    async def update_message(self, broadcast_id: int, message: BroadcastMessageDto) -> None:
        await self.uow.repository.broadcasts.update_message(
            broadcast_id=broadcast_id,
            user_id=message.user_id,
            **message.changed_data,
        )

    async def bulk_update_messages(self, messages: list[BroadcastMessageDto]) -> None:
        await self.uow.repository.broadcasts.bulk_update_messages(
            data=[m.model_dump() for m in messages],
        )

    async def delete_broadcast(self, broadcast_id: int) -> None:
        await self.uow.repository.broadcasts._delete(Broadcast, Broadcast.id == broadcast_id)

    async def get_status(self, task_id: UUID) -> Optional[BroadcastStatus]:
        db_broadcast = await self.uow.repository.broadcasts.get(task_id)
        return db_broadcast.status if db_broadcast else None

    #

    async def get_audience_count(
        self,
        audience: BroadcastAudience,
        plan_id: Optional[int] = None,
    ) -> int:
        logger.debug(f"Counting audience '{audience}' for plan '{plan_id}'")

        is_not_block = and_(
            User.is_blocked.is_(False),
            User.is_bot_blocked.is_(False),
        )

        if audience == BroadcastAudience.PLAN:
            if plan_id:
                db_subs = await self.uow.repository.subscriptions.filter_by_plan_id(plan_id)
                active_subs = [
                    s
                    for s in db_subs
                    if s.status == SubscriptionStatus.ACTIVE
                    and not s.user.is_blocked
                    and not s.user.is_bot_blocked
                ]
                return len(active_subs)

            count = await self.uow.repository.plans._count(
                Plan,
                Plan.availability != PlanAvailability.TRIAL,
            )
            logger.debug(f"Audience count for '{audience}' (plan={plan_id}) is '{count}'")
            return count

        if audience == BroadcastAudience.ALL:
            return await self.uow.repository.users._count(User, is_not_block)

        if audience == BroadcastAudience.SUBSCRIBED:
            conditions = and_(
                is_not_block,
                User.current_subscription.has(Subscription.status == SubscriptionStatus.ACTIVE),
            )
            return await self.uow.repository.users._count(User, conditions)

        if audience == BroadcastAudience.UNSUBSCRIBED:
            conditions = and_(
                is_not_block,
                User.current_subscription_id.is_(None),
            )
            return await self.uow.repository.users._count(User, conditions)

        if audience == BroadcastAudience.EXPIRED:
            conditions = and_(
                is_not_block,
                User.current_subscription.has(Subscription.status == SubscriptionStatus.EXPIRED),
            )
            return await self.uow.repository.users._count(User, conditions)

        if audience == BroadcastAudience.TRIAL:
            conditions = and_(
                is_not_block,
                User.current_subscription.has(Subscription.is_trial.is_(True)),
            )
            return await self.uow.repository.users._count(User, conditions)

        raise Exception(f"Unknown broadcast audience: {audience}")

    async def get_audience_users(
        self,
        audience: BroadcastAudience,
        plan_id: Optional[int] = None,
    ) -> list[UserDto]:
        logger.debug(f"Retrieving users for audience '{audience}', plan_id: {plan_id}")

        is_not_block = and_(
            User.is_blocked.is_(False),
            User.is_bot_blocked.is_(False),
        )

        if audience == BroadcastAudience.PLAN and plan_id:
            db_subscriptions = await self.uow.repository.subscriptions.filter_by_plan_id(plan_id)
            active_subs = [
                s
                for s in db_subscriptions
                if s.status == SubscriptionStatus.ACTIVE
                and not s.user.is_blocked
                and not s.user.is_bot_blocked
            ]
            user_ids = [sub.user_telegram_id for sub in active_subs]
            db_users = await self.uow.repository.users.get_by_ids(telegram_ids=user_ids)
            logger.debug(
                f"Retrieved '{len(db_users)}' users for audience '{audience}' (plan={plan_id})"
            )
            return UserDto.from_model_list(db_users)

        if audience == BroadcastAudience.ALL:
            db_users = await self.uow.repository.users._get_many(User, is_not_block)
            return UserDto.from_model_list(db_users)

        if audience == BroadcastAudience.SUBSCRIBED:
            conditions = and_(
                is_not_block,
                User.current_subscription.has(Subscription.status == SubscriptionStatus.ACTIVE),
            )
            db_users = await self.uow.repository.users._get_many(User, conditions)
            return UserDto.from_model_list(db_users)

        if audience == BroadcastAudience.UNSUBSCRIBED:
            conditions = and_(is_not_block, User.current_subscription_id.is_(None))
            db_users = await self.uow.repository.users._get_many(User, conditions)
            return UserDto.from_model_list(db_users)

        if audience == BroadcastAudience.EXPIRED:
            conditions = and_(
                is_not_block,
                User.current_subscription.has(Subscription.status == SubscriptionStatus.EXPIRED),
            )
            db_users = await self.uow.repository.users._get_many(User, conditions)
            return UserDto.from_model_list(db_users)

        if audience == BroadcastAudience.TRIAL:
            conditions = and_(
                is_not_block,
                User.current_subscription.has(Subscription.is_trial.is_(True)),
            )
            db_users = await self.uow.repository.users._get_many(User, conditions)
            return UserDto.from_model_list(db_users)

        raise Exception(f"Unknown broadcast audience: {audience}")
