from datetime import timedelta
from typing import Optional, cast
from uuid import UUID

from adaptix import Retort
from adaptix.conversion import ConversionRetort
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.dao import BroadcastDao
from src.application.dto import BroadcastDto, BroadcastMessageDto
from src.core.enums import BroadcastMessageStatus, BroadcastStatus
from src.core.utils.time import datetime_now
from src.infrastructure.database.models import Broadcast, BroadcastMessage


class BroadcastDaoImpl(BroadcastDao):
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

        self._convert_to_dto = self.conversion_retort.get_converter(Broadcast, BroadcastDto)
        self._convert_to_dto_list = self.conversion_retort.get_converter(
            list[Broadcast], list[BroadcastDto]
        )
        self._convert_to_dto_messages_list = self.conversion_retort.get_converter(
            list[BroadcastMessage], list[BroadcastMessageDto]
        )

    async def create(self, broadcast: BroadcastDto) -> BroadcastDto:
        broadcast_data = self.retort.dump(broadcast)
        db_broadcast = Broadcast(**broadcast_data)

        self.session.add(db_broadcast)
        await self.session.flush()

        logger.debug(f"New broadcast task '{broadcast.task_id}' created")
        return self._convert_to_dto(db_broadcast)

    async def get_by_task_id(self, task_id: UUID) -> Optional[BroadcastDto]:
        stmt = select(Broadcast).where(Broadcast.task_id == task_id)
        db_broadcast = await self.session.scalar(stmt)

        if db_broadcast:
            logger.debug(f"Broadcast task '{task_id}' found")
            return self._convert_to_dto(db_broadcast)

        logger.debug(f"Broadcast task '{task_id}' not found")
        return None

    async def get_all(self) -> list[BroadcastDto]:
        stmt = select(Broadcast).order_by(Broadcast.created_at.desc())
        result = await self.session.scalars(stmt)
        db_broadcasts = cast(list, result.all())

        logger.debug(f"Retrieved '{len(db_broadcasts)}' broadcasts")
        return self._convert_to_dto_list(db_broadcasts)

    async def update_status(self, task_id: UUID, status: BroadcastStatus) -> None:
        stmt = update(Broadcast).where(Broadcast.task_id == task_id).values(status=status)
        await self.session.execute(stmt)
        logger.debug(f"Broadcast task '{task_id}' status updated to '{status}'")

    async def add_messages(
        self, task_id: UUID, messages: list[BroadcastMessageDto]
    ) -> list[BroadcastMessageDto]:
        broadcast_id_stmt = select(Broadcast.id).where(Broadcast.task_id == task_id)
        broadcast_id = await self.session.scalar(broadcast_id_stmt)

        if not broadcast_id:
            logger.error(f"Failed to add messages: broadcast task '{task_id}' not found")
            return []

        db_messages = [
            BroadcastMessage(**self.retort.dump(msg), broadcast_id=broadcast_id) for msg in messages
        ]
        self.session.add_all(db_messages)
        await self.session.flush()

        logger.debug(f"Added '{len(messages)}' messages to broadcast task '{task_id}'")
        return self._convert_to_dto_messages_list(db_messages)

    async def update_message_status(
        self,
        task_id: UUID,
        telegram_id: int,
        status: BroadcastMessageStatus,
        message_id: Optional[int] = None,
    ) -> None:
        broadcast_id_stmt = (
            select(Broadcast.id).where(Broadcast.task_id == task_id).scalar_subquery()
        )

        stmt = (
            update(BroadcastMessage)
            .where(
                BroadcastMessage.broadcast_id == broadcast_id_stmt,
                BroadcastMessage.user_telegram_id == telegram_id,
            )
            .values(status=status, message_id=message_id)
        )
        await self.session.execute(stmt)
        logger.debug(
            f"Message status for user '{telegram_id}' in task '{task_id}' updated to '{status}'"
        )

    async def update_stats(self, task_id: UUID, success_count: int, failed_count: int) -> None:
        stmt = (
            update(Broadcast)
            .where(Broadcast.task_id == task_id)
            .values(
                success_count=Broadcast.success_count + success_count,
                failed_count=Broadcast.failed_count + failed_count,
            )
        )
        await self.session.execute(stmt)
        logger.debug(
            f"Incremented stats for task '{task_id}': "
            f"success={success_count}, failed={failed_count}"
        )

    async def get_active(self) -> list[BroadcastDto]:
        stmt = select(Broadcast).where(Broadcast.status == BroadcastStatus.PROCESSING)
        result = await self.session.scalars(stmt)
        db_broadcasts = cast(list, result.all())

        logger.debug(f"Retrieved '{len(db_broadcasts)}' active broadcasts")
        return self._convert_to_dto_list(db_broadcasts)

    async def delete_old(self, days: int = 7) -> int:
        threshold = datetime_now() - timedelta(days=days)

        stmt = delete(Broadcast).where(Broadcast.created_at < threshold).returning(Broadcast.id)
        result = await self.session.execute(stmt)
        deleted_ids = result.scalars().all()
        count = len(deleted_ids)

        if count > 0:
            logger.debug(f"Deleted '{count}' old broadcasts older than '{days}' days")
        else:
            logger.debug(f"No old broadcasts found to delete for the last '{days}' days")

        return count

    async def bulk_update_messages(self, messages: list[BroadcastMessageDto]) -> None:
        if not messages:
            logger.debug("No broadcast messages to update in bulk")
            return

        stmt = update(BroadcastMessage)

        data = [
            {
                "id": msg.id,
                "status": msg.status,
                "message_id": msg.message_id,
            }
            for msg in messages
        ]

        await self.session.execute(stmt, data, execution_options={"synchronize_session": None})
        logger.debug(f"Bulk updated '{len(data)}' broadcast messages")
