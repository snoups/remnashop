from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.event_outbox import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from app.modules.users.usecases import AcceptRulesUseCase


async def test_accepting_rules_stamps_the_user_and_records_the_event(
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session: AsyncSession,
) -> None:
    user = await user_repository.create(CreateUserDto(name="r", telegram_id=820_001))

    updated = await AcceptRulesUseCase(user_repository, uow, event_publisher)(user)

    assert updated.rules_accepted_at is not None
    stored = await user_repository.find_by_id(user.id)
    assert stored is not None and stored.rules_accepted_at == updated.rules_accepted_at
    events = (
        await session.scalars(
            select(EventOutboxEntry).where(EventOutboxEntry.event_type == "UserRulesAcceptedEvent")
        )
    ).all()
    assert [event.actor_id for event in events] == [user.id]
