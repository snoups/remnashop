from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import TransactionStatus
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import TransactionDto, UserDto
from src.infrastructure.database.models.sql import Transaction
from src.infrastructure.redis import RedisRepository

from .base import BaseService


class TransactionService(BaseService):
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

    async def create(self, user: UserDto, transaction: TransactionDto) -> TransactionDto:
        db_transaction = Transaction(
            **transaction.model_dump(exclude={"user"}, mode="json"),
            user_telegram_id=user.telegram_id,
        )
        db_created_transaction = await self.uow.repository.transactions.create(db_transaction)
        return TransactionDto.from_model(db_created_transaction)  # type: ignore[return-value]

    async def get(self, payment_id: UUID) -> Optional[TransactionDto]:
        db_transaction = await self.uow.repository.transactions.get(payment_id)
        return TransactionDto.from_model(db_transaction)

    async def get_by_user(self, telegram_id: int) -> list[TransactionDto]:
        db_transaction = await self.uow.repository.transactions.get_by_user(telegram_id)
        return TransactionDto.from_model_list(db_transaction)

    async def update(self, transaction: TransactionDto) -> Optional[TransactionDto]:
        db_updated_transaction = await self.uow.repository.transactions.update(
            payment_id=transaction.payment_id,
            **transaction.changed_data,
        )
        return TransactionDto.from_model(db_updated_transaction)

    async def count(self) -> int:
        return await self.uow.repository.transactions.count()

    async def count_by_status(self, status: TransactionStatus) -> int:
        return await self.uow.repository.transactions.count_by_status(status)
