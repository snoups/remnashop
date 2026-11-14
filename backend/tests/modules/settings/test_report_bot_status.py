from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.modules.settings.dto import BotStatusKind, ReportBotStatusDto
from app.modules.settings.usecases import ReportBotStatusUseCase


async def test_channel_check_failure_reports_once_per_hour(
    session: AsyncSession, redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = ReportBotStatusUseCase(uow, event_publisher, redis)
    dto = ReportBotStatusDto(
        kind=BotStatusKind.CHANNEL_CHECK_FAILED, detail="chat not found", channel_id=-100
    )

    await use_case.system(dto)
    await use_case.system(dto)

    rows = (await session.execute(select(EventOutboxEntry))).scalars().all()
    assert [row.event_type for row in rows] == ["RequiredChannelCheckFailedEvent"]
    assert rows[0].payload == {"channel_id": -100, "error": "chat not found"}


async def test_started_and_stopped_are_always_reported(
    session: AsyncSession, redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = ReportBotStatusUseCase(uow, event_publisher, redis)

    await use_case.system(ReportBotStatusDto(kind=BotStatusKind.STARTED, detail="shop_bot"))
    await use_case.system(ReportBotStatusDto(kind=BotStatusKind.STOPPED))

    rows = (
        (await session.execute(select(EventOutboxEntry.event_type).order_by(EventOutboxEntry.id)))
        .scalars()
        .all()
    )
    assert list(rows) == ["BotStartedEvent", "BotStoppedEvent"]
