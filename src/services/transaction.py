from typing import Optional
from uuid import UUID

from aiogram import Bot
from fluentogram import TranslatorHub
from loguru import logger
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
        data = transaction.model_dump(exclude={"user"})
        data["plan"] = transaction.plan.model_dump(mode="json")
        data["pricing"] = transaction.pricing.model_dump(mode="json")

        db_transaction = Transaction(**data, user_telegram_id=user.telegram_id)
        db_created_transaction = await self.uow.repository.transactions.create(db_transaction)
        logger.info(f"Created transaction '{transaction.payment_id}' for user '{user.telegram_id}'")
        return TransactionDto.from_model(db_created_transaction)  # type: ignore[return-value]

    async def get(self, payment_id: UUID) -> Optional[TransactionDto]:
        db_transaction = await self.uow.repository.transactions.get(payment_id)

        if db_transaction:
            logger.debug(f"Retrieved transaction '{payment_id}'")
        else:
            logger.warning(f"Transaction '{payment_id}' not found")

        return TransactionDto.from_model(db_transaction)

    async def get_by_user(self, telegram_id: int) -> list[TransactionDto]:
        db_transactions = await self.uow.repository.transactions.get_by_user(telegram_id)
        logger.debug(f"Retrieved '{len(db_transactions)}' transactions for user '{telegram_id}'")
        return TransactionDto.from_model_list(db_transactions)

    async def get_all(self) -> list[TransactionDto]:
        db_transactions = await self.uow.repository.transactions.get_all()
        logger.debug(f"Retrieved '{len(db_transactions)}' total transactions")
        return TransactionDto.from_model_list(db_transactions)

    async def get_by_status(self, status: TransactionStatus) -> list[TransactionDto]:
        db_transactions = await self.uow.repository.transactions.get_by_status(status)
        logger.debug(f"Retrieved '{len(db_transactions)}' transactions with status '{status}'")
        return TransactionDto.from_model_list(db_transactions)

    async def update(self, transaction: TransactionDto) -> Optional[TransactionDto]:
        db_updated_transaction = await self.uow.repository.transactions.update(
            payment_id=transaction.payment_id,
            **transaction.changed_data,
        )

        if db_updated_transaction:
            logger.info(f"Updated transaction '{transaction.payment_id}' successfully")
        else:
            logger.warning(
                f"Attempted to update transaction '{transaction.payment_id}', "
                "but transaction was not found or update failed"
            )

        return TransactionDto.from_model(db_updated_transaction)

    async def count(self) -> int:
        count = await self.uow.repository.transactions.count()
        logger.debug(f"Total transactions count: '{count}'")
        return count

    async def count_by_status(self, status: TransactionStatus) -> int:
        count = await self.uow.repository.transactions.count_by_status(status)
        logger.debug(f"Transactions count with status '{status}': '{count}'")
        return count
