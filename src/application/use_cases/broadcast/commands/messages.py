from dataclasses import dataclass
from uuid import UUID

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import BroadcastDao
from src.application.common.uow import UnitOfWork
from src.application.dto import BroadcastMessageDto, UserDto
from src.core.enums import BroadcastMessageStatus


@dataclass(frozen=True)
class InitializeBroadcastMessagesDto:
    task_id: UUID
    messages: list[BroadcastMessageDto]


class InitializeBroadcastMessages(
    Interactor[InitializeBroadcastMessagesDto, list[BroadcastMessageDto]],
):
    required_permission = None

    def __init__(self, uow: UnitOfWork, broadcast_dao: BroadcastDao) -> None:
        self.uow = uow
        self.broadcast_dao = broadcast_dao

    async def _execute(
        self,
        actor: UserDto,
        data: InitializeBroadcastMessagesDto,
    ) -> list[BroadcastMessageDto]:
        async with self.uow:
            messages = await self.broadcast_dao.add_messages(data.task_id, data.messages)
            await self.uow.commit()

        logger.info(f"Initialized {len(data.messages)} messages for broadcast '{data.task_id}'")
        return messages


@dataclass(frozen=True)
class UpdateBroadcastMessageStatusDto:
    task_id: UUID
    messages: list[BroadcastMessageDto]


class UpdateBroadcastMessageStatus(Interactor[UpdateBroadcastMessageStatusDto, None]):
    required_permission = None

    def __init__(self, uow: UnitOfWork, broadcast_dao: BroadcastDao) -> None:
        self.uow = uow
        self.broadcast_dao = broadcast_dao

    async def _execute(self, actor: UserDto, data: UpdateBroadcastMessageStatusDto) -> None:
        success_count = sum(1 for m in data.messages if m.status == BroadcastMessageStatus.SENT)
        failed_count = len(data.messages) - success_count

        async with self.uow:
            await self.broadcast_dao.bulk_update_messages(data.messages)
            await self.broadcast_dao.update_stats(
                data.task_id,
                success_count=success_count,
                failed_count=failed_count,
            )
            await self.uow.commit()


class BulkUpdateBroadcastMessages(Interactor[list[BroadcastMessageDto], None]):
    required_permission = None

    def __init__(self, uow: UnitOfWork, broadcast_dao: BroadcastDao) -> None:
        self.uow = uow
        self.broadcast_dao = broadcast_dao

    async def _execute(self, actor: UserDto, data: list[BroadcastMessageDto]) -> None:
        async with self.uow:
            await self.broadcast_dao.bulk_update_messages(data)
            await self.uow.commit()

        logger.info(f"Bulk updated {len(data)} messages status")
