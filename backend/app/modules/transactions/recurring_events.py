from dataclasses import dataclass
from typing import ClassVar, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.enums import Currency
from app.core.events import EventCategory, SystemEvent
from app.core.outbox_event_publisher import _build_payload


@dataclass(frozen=True, kw_only=True)
class RecurringPaymentUpcomingEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    user_id: int
    subscription_id: int
    amount: str
    currency: Currency
    scheduled_at: str


@dataclass(frozen=True, kw_only=True)
class RecurringPaymentFailedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    user_id: int
    subscription_id: int
    order_id: int
    amount: str
    currency: Currency
    reason: str
    next_attempt_at: Optional[str] = None
    attempt: int = 0


@dataclass(frozen=True, kw_only=True)
class RecurringPaymentPausedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    user_id: int
    subscription_id: int
    reason: str
    order_id: Optional[int] = None
    next_attempt_at: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class RecurringPaymentExhaustedEvent(SystemEvent):
    category: ClassVar[EventCategory] = EventCategory.PAYMENT
    user_id: int
    subscription_id: int
    reason: str
    order_id: Optional[int] = None


async def persist_recurring_event(session: AsyncSession, event: SystemEvent) -> None:
    # A repository transition and its notice must commit together. The durable
    # outbox sweep delivers this even when no immediate broker kick is possible.
    session.add(
        EventOutboxEntry(
            category=event.category,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            ip_address=event.ip_address,
            payload=_build_payload(event),
        )
    )
    await session.flush()
