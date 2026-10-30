from datetime import datetime, timedelta
from typing import Final, Optional, cast

from sqlalchemy import ColumnElement, CursorResult, delete, or_, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user_session import UserSession
from app.core.enums import SessionAudience
from app.core.utils.time import datetime_now
from app.modules.auth.dto import CreateSessionDto, SessionDto

_ROTATION_GRACE_SECONDS: Final[int] = 30


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: UserSession) -> SessionDto:
        return SessionDto.model_validate(row, from_attributes=True)

    def _active_clause(self) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
        now = datetime_now()
        return (UserSession.revoked_at.is_(None), UserSession.expires_at > now)

    async def create(self, data: CreateSessionDto) -> SessionDto:
        now = datetime_now()
        row = UserSession(
            user_id=data.user_id,
            refresh_token_hash=data.refresh_token_hash,
            ip_address=data.ip_address,
            user_agent=data.user_agent,
            last_used_at=now,
            expires_at=data.expires_at,
            audience=data.audience,
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_dto(row)

    async def find_active_by_id(self, session_id: int) -> Optional[SessionDto]:
        stmt = select(UserSession).where(UserSession.id == session_id, *self._active_clause())
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def find_by_current_hash(self, refresh_token_hash: str) -> Optional[SessionDto]:
        stmt = select(UserSession).where(
            UserSession.refresh_token_hash == refresh_token_hash, *self._active_clause()
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def find_by_previous_hash_in_grace(self, refresh_token_hash: str) -> Optional[SessionDto]:
        now = datetime_now()
        stmt = select(UserSession).where(
            UserSession.previous_refresh_token_hash == refresh_token_hash,
            UserSession.previous_hash_grace_until.is_not(None),
            UserSession.previous_hash_grace_until > now,
            *self._active_clause(),
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def find_rotatable_by_hash(self, refresh_token_hash: str) -> Optional[SessionDto]:
        current = await self.find_by_current_hash(refresh_token_hash)
        if current is not None:
            return current
        return await self.find_by_previous_hash_in_grace(refresh_token_hash)

    async def find_by_expired_previous_hash(self, refresh_token_hash: str) -> Optional[SessionDto]:
        # tells "the previous hash, past its grace window" (theft) from "never
        # issued" (invalid token); the current/in-grace lookups miss on both
        now = datetime_now()
        stmt = select(UserSession).where(
            UserSession.previous_refresh_token_hash == refresh_token_hash,
            UserSession.previous_hash_grace_until.is_not(None),
            UserSession.previous_hash_grace_until <= now,
            *self._active_clause(),
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def list_active_by_user(self, user_id: int) -> list[SessionDto]:
        stmt = (
            select(UserSession)
            .where(UserSession.user_id == user_id, *self._active_clause())
            .order_by(UserSession.last_used_at.desc())
        )
        rows = await self.session.scalars(stmt)
        return [self._to_dto(row) for row in rows]

    async def rotate(
        self, session_id: int, new_refresh_token_hash: str, *, extend_grace: bool = True
    ) -> SessionDto:
        stmt = select(UserSession).where(UserSession.id == session_id).with_for_update()
        row = await self.session.scalar(stmt)
        assert row is not None
        now = datetime_now()
        if extend_grace:
            row.previous_refresh_token_hash = row.refresh_token_hash
            row.previous_hash_grace_until = now + timedelta(seconds=_ROTATION_GRACE_SECONDS)
        row.refresh_token_hash = new_refresh_token_hash
        row.last_used_at = now
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def revoke_by_id(self, session_id: int) -> None:
        row = await self.session.get(UserSession, session_id)
        if row is not None:
            row.revoked_at = datetime_now()
            await self.session.flush()

    async def revoke_active_by_fingerprint(
        self,
        user_id: int,
        ip_address: str,
        user_agent: Optional[str],
        audience: SessionAudience,
    ) -> None:
        # logging in again from the same device replaces the old session; with
        # no device id, ip_address + user_agent is the fingerprint
        now = datetime_now()
        user_agent_clause = (
            UserSession.user_agent.is_(None)
            if user_agent is None
            else UserSession.user_agent == user_agent
        )
        stmt = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.ip_address == ip_address,
                UserSession.audience == audience,
                user_agent_clause,
                *self._active_clause(),
            )
            .values(revoked_at=now)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def revoke_all_by_user(
        self,
        user_id: int,
        *,
        keep_session_id: Optional[int] = None,
        audience: Optional[SessionAudience] = None,
    ) -> None:
        now = datetime_now()
        stmt = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.id != keep_session_id if keep_session_id is not None else true(),
                UserSession.audience == audience if audience is not None else true(),
                *self._active_clause(),
            )
            .values(revoked_at=now)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def revoke_all_by_audience(self, audience: SessionAudience) -> None:
        stmt = (
            update(UserSession)
            .where(UserSession.audience == audience, *self._active_clause())
            .values(revoked_at=datetime_now())
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def delete_stale(self, cutoff: datetime) -> int:
        stmt = delete(UserSession).where(
            or_(UserSession.expires_at < cutoff, UserSession.revoked_at < cutoff)
        )
        result = await self.session.execute(stmt)
        return cast(CursorResult, result).rowcount
