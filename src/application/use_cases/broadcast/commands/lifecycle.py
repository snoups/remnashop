from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import BroadcastDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import BroadcastDto, MessagePayloadDto, UserDto
from src.application.use_cases.broadcast.queries.audience import (
    GetBroadcastAudienceCount,
    GetBroadcastAudienceCountDto,
)
from src.core.enums import BroadcastAudience, BroadcastStatus


@dataclass(frozen=True)
class StartBroadcastDto:
    audience: BroadcastAudience
    payload: MessagePayloadDto
    plan_id: Optional[int] = None


class StartBroadcast(Interactor[StartBroadcastDto, UUID]):
    required_permission = Permission.BROADCAST

    def __init__(
        self,
        uow: UnitOfWork,
        broadcast_dao: BroadcastDao,
        get_broadcast_audience_count: GetBroadcastAudienceCount,
    ) -> None:
        self.uow = uow
        self.broadcast_dao = broadcast_dao
        self.get_broadcast_audience_count = get_broadcast_audience_count

    async def _execute(self, actor: UserDto, data: StartBroadcastDto) -> UUID:
        from src.infrastructure.taskiq.tasks.broadcast import send_broadcast_task  # noqa: PLC0415

        total_count = await self.get_broadcast_audience_count.system(
            GetBroadcastAudienceCountDto(data.audience, data.plan_id)
        )

        async with self.uow:
            task_id = uuid4()
            broadcast = BroadcastDto(
                task_id=task_id,
                status=BroadcastStatus.PROCESSING,
                total_count=total_count,
                audience=data.audience,
                payload=data.payload,
            )
            await self.broadcast_dao.create(broadcast)
            await self.uow.commit()

            await (
                send_broadcast_task.kicker()
                .with_task_id(str(task_id))
                .kiq(
                    broadcast,
                    data.plan_id,
                )  # type: ignore[call-overload]
            )

        logger.info(f"{actor.log} Scheduled broadcast initialization '{task_id}'")
        return task_id


@dataclass(frozen=True)
class DeleteBroadcastResultDto:
    total: int
    deleted: int
    failed: int


class DeleteBroadcast(Interactor[UUID, DeleteBroadcastResultDto]):
    required_permission = Permission.BROADCAST

    def __init__(
        self,
        uow: UnitOfWork,
        broadcast_dao: BroadcastDao,
    ) -> None:
        self.uow = uow
        self.broadcast_dao = broadcast_dao

    async def _execute(self, actor: UserDto, data: UUID) -> DeleteBroadcastResultDto:
        from src.infrastructure.taskiq.tasks.broadcast import delete_broadcast_task  # noqa: PLC0415

        async with self.uow:
            broadcast = await self.broadcast_dao.get_by_task_id(data)

            if not broadcast:
                logger.error(f"{actor.log} Failed to find broadcast '{data}' for deletion")
                raise ValueError(f"Broadcast '{data}' not found")

            if broadcast.status == BroadcastStatus.DELETED:
                logger.warning(f"{actor.log} Broadcast '{data}' is already deleted")
                raise ValueError("Broadcast already deleted")

            await self.broadcast_dao.update_status(data, BroadcastStatus.DELETED)
            await self.uow.commit()

        logger.info(f"{actor.log} Initiated deletion for broadcast '{data}'")

        task = await delete_broadcast_task.kiq(broadcast)  # type: ignore[call-overload]
        result = await task.wait_result()
        counts = result.return_value

        logger.info(
            f"{actor.log} Finished deletion for '{data}' "
            f"(total: '{counts[0]}', deleted: '{counts[1]}', failed: '{counts[2]}')"
        )
        return DeleteBroadcastResultDto(total=counts[0], deleted=counts[1], failed=counts[2])


class CancelBroadcast(Interactor[UUID, None]):
    required_permission = Permission.BROADCAST

    def __init__(self, uow: UnitOfWork, broadcast_dao: BroadcastDao) -> None:
        self.uow = uow
        self.broadcast_dao = broadcast_dao

    async def _execute(self, actor: UserDto, data: UUID) -> None:
        async with self.uow:
            broadcast = await self.broadcast_dao.get_by_task_id(data)

            if not broadcast:
                logger.error(f"{actor.log} Attempted to cancel non-existent broadcast '{data}'")
                raise ValueError(f"Broadcast '{data}' not found")

            if broadcast.status != BroadcastStatus.PROCESSING:
                logger.warning(
                    f"{actor.log} Failed to cancel broadcast '{data}' "
                    f"with status '{broadcast.status}'"
                )
                raise ValueError("Broadcast is not cancelable")

            await self.broadcast_dao.update_status(data, BroadcastStatus.CANCELED)
            await self.uow.commit()

        logger.info(f"{actor.log} Canceled broadcast '{data}'")


@dataclass(frozen=True)
class FinishBroadcastDto:
    task_id: UUID
    status: BroadcastStatus


class FinishBroadcast(Interactor[FinishBroadcastDto, None]):
    required_permission = None

    def __init__(self, uow: UnitOfWork, broadcast_dao: BroadcastDao) -> None:
        self.uow = uow
        self.broadcast_dao = broadcast_dao

    async def _execute(self, actor: UserDto, data: FinishBroadcastDto) -> None:
        async with self.uow:
            await self.broadcast_dao.update_status(data.task_id, data.status)
            await self.uow.commit()

        logger.info(f"Finished broadcast '{data.task_id}' with status '{data.status}'")
