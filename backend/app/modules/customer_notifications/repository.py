from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.customer_notification import CustomerNotification
from app.core.utils.time import datetime_now
from app.modules.customer_notifications.dto import CustomerNotificationDto


class CustomerNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        user_id: int,
        outbox_id: int,
        event_type: str,
        args: dict[str, Any],
        subscription_id: Optional[int],
    ) -> None:
        await self.session.execute(
            pg_insert(CustomerNotification)
            .values(
                user_id=user_id,
                outbox_id=outbox_id,
                event_type=event_type,
                args=args,
                subscription_id=subscription_id,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "outbox_id"])
        )

    async def list_recent(
        self, user_id: int, *, since: datetime, limit: int
    ) -> list[CustomerNotificationDto]:
        rows = await self.session.scalars(
            select(CustomerNotification)
            .where(
                CustomerNotification.user_id == user_id, CustomerNotification.created_at >= since
            )
            .order_by(CustomerNotification.created_at.desc(), CustomerNotification.id.desc())
            .limit(limit)
        )
        return [
            CustomerNotificationDto(
                id=r.id,
                event_type=r.event_type,
                args=r.args,
                subscription_id=r.subscription_id,
                created_at=r.created_at,
                read_at=r.read_at,
            )
            for r in rows
        ]

    async def count_unread(self, user_id: int, *, since: datetime) -> int:
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(CustomerNotification)
                .where(
                    CustomerNotification.user_id == user_id,
                    CustomerNotification.created_at >= since,
                    CustomerNotification.read_at.is_(None),
                )
            )
        ) or 0

    async def mark_all_read(self, user_id: int) -> None:
        await self.session.execute(
            update(CustomerNotification)
            .where(CustomerNotification.user_id == user_id, CustomerNotification.read_at.is_(None))
            .values(read_at=datetime_now())
        )

    async def delete_for_user(self, user_id: int) -> None:
        await self.session.execute(
            delete(CustomerNotification).where(CustomerNotification.user_id == user_id)
        )

    async def delete_older_than(self, cutoff: datetime) -> int:
        result = await self.session.execute(
            delete(CustomerNotification).where(CustomerNotification.created_at < cutoff)
        )
        return int(getattr(result, "rowcount", 0) or 0)
