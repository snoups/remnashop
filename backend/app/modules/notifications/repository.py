from typing import Final, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.notification_settings import NotificationSettings
from app.core.db.models.push_subscription import PushSubscription
from app.core.db.models.user_session import UserSession
from app.core.db.singleton import SINGLETON_ID, get_or_create_singleton
from app.core.enums import SessionAudience
from app.core.utils.time import datetime_now
from app.modules.notifications.dto import (
    NotificationSettingsDto,
    PushSubscriptionDto,
    UpdateNotificationSettingsDto,
)

_MAX_PUSH_FAILURES: Final[int] = 3


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_settings_dto(self, row: Optional[NotificationSettings]) -> NotificationSettingsDto:
        if row is None:
            return NotificationSettingsDto()
        return NotificationSettingsDto.model_validate(row, from_attributes=True)

    def _to_push_subscription_dto(self, row: PushSubscription) -> PushSubscriptionDto:
        return PushSubscriptionDto.model_validate(row, from_attributes=True)

    async def get_settings(self) -> NotificationSettingsDto:
        return self._to_settings_dto(await self.session.get(NotificationSettings, SINGLETON_ID))

    async def is_push_configured(self) -> bool:
        return (await self.get_settings()).is_push_configured

    async def set_vapid_keys(self, public_key: str, private_key: str) -> NotificationSettingsDto:
        row = await get_or_create_singleton(self.session, NotificationSettings, SINGLETON_ID)
        row.vapid_public_key = public_key
        row.vapid_private_key = private_key
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_settings_dto(row)

    async def update_settings(self, data: UpdateNotificationSettingsDto) -> NotificationSettingsDto:
        row = await get_or_create_singleton(self.session, NotificationSettings, SINGLETON_ID)
        if data.vapid_contact is not None:
            row.vapid_contact = data.vapid_contact or None
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_settings_dto(row)

    async def upsert_push_subscription(
        self,
        *,
        user_id: int,
        session_id: int,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: Optional[str],
    ) -> tuple[PushSubscriptionDto, bool]:
        existing = await self.session.scalar(
            select(PushSubscription.id).where(PushSubscription.endpoint == endpoint)
        )
        values = {
            "user_id": user_id,
            "session_id": session_id,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": user_agent,
            "failure_count": 0,
            "last_seen_at": datetime_now(),
        }
        stmt = (
            pg_insert(PushSubscription)
            .values(endpoint=endpoint, **values)
            .on_conflict_do_update(index_elements=["endpoint"], set_=values)
            .returning(PushSubscription)
        )
        row = (await self.session.execute(stmt)).scalar_one()
        await self.session.flush()
        return self._to_push_subscription_dto(row), existing is None

    async def list_push_subscriptions(
        self, user_id: int, audience: SessionAudience
    ) -> list[PushSubscriptionDto]:
        # only devices whose signing-in session is still live
        rows = await self.session.scalars(
            select(PushSubscription)
            .join(UserSession, UserSession.id == PushSubscription.session_id)
            .where(
                PushSubscription.user_id == user_id,
                UserSession.audience == audience,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime_now(),
            )
            .order_by(PushSubscription.last_seen_at.desc())
        )
        return [self._to_push_subscription_dto(r) for r in rows]

    async def delete_all_push_subscriptions(self) -> int:
        result = await self.session.execute(delete(PushSubscription))
        return int(getattr(result, "rowcount", 0) or 0)

    async def delete_push_subscription(self, subscription_id: int, user_id: int) -> bool:
        result = await self.session.execute(
            delete(PushSubscription).where(
                PushSubscription.id == subscription_id, PushSubscription.user_id == user_id
            )
        )
        return bool(getattr(result, "rowcount", 0))

    async def record_push_success(self, subscription_id: int) -> None:
        row = await self.session.get(PushSubscription, subscription_id)
        if row is not None:
            row.failure_count = 0
            row.last_seen_at = datetime_now()
            await self.session.flush()

    async def record_push_failure(self, subscription_id: int, *, gone: bool) -> None:
        row = await self.session.get(PushSubscription, subscription_id)
        if row is None:
            return
        row.failure_count += 1
        if gone or row.failure_count >= _MAX_PUSH_FAILURES:
            await self.session.delete(row)
        await self.session.flush()
