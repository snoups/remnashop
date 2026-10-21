from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.uow import UnitOfWork
from app.core.outbox_event_publisher import OutboxEventPublisher
from app.modules.auth import RescueCliAction, RescueCliUsedEvent


class _SweepDelivers:
    # no broker here: the worker's outbox sweep picks the row up within a minute
    async def kiq(self, *, outbox_id: int) -> None:
        return None


async def record_rescue(
    session: AsyncSession, action: RescueCliAction, user_id: Optional[int] = None
) -> None:
    """Writes the action to the outbox in the caller's transaction, so the audit
    log and the security notification see it like any dashboard action."""
    publisher = OutboxEventPublisher(UnitOfWork(session), _SweepDelivers())
    await publisher.publish(RescueCliUsedEvent(action=action, user_id=user_id))
