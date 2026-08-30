from datetime import datetime, timedelta, timezone
from typing import Optional, cast

from sqlalchemy import ColumnElement, CursorResult, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.oauth_identity import OAuthIdentity
from app.core.db.models.user_session import UserSession
from app.core.enums import OAuthProvider
from app.modules.auth.dto import (
    CreateOAuthIdentityDto,
    CreateSessionDto,
    OAuthIdentityDto,
    SessionDto,
)

_ROTATION_GRACE_SECONDS = 30


class OAuthIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: OAuthIdentity) -> OAuthIdentityDto:
        return OAuthIdentityDto.model_validate(row, from_attributes=True)

    async def create(self, data: CreateOAuthIdentityDto) -> OAuthIdentityDto:
        existing = await self.session.scalar(
            select(OAuthIdentity).where(
                OAuthIdentity.user_id == data.user_id, OAuthIdentity.provider == data.provider
            )
        )

        if existing is not None:
            existing.external_id = data.external_id
            existing.external_login = data.external_login
            await self.session.flush()
            await self.session.refresh(existing)
            return self._to_dto(existing)

        row = OAuthIdentity(
            user_id=data.user_id,
            provider=data.provider,
            external_id=data.external_id,
            external_login=data.external_login,
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_dto(row)

    async def get_by_provider_external_id(
        self,
        provider: OAuthProvider,
        external_id: str,
    ) -> Optional[OAuthIdentityDto]:
        stmt = select(OAuthIdentity).where(
            OAuthIdentity.provider == provider, OAuthIdentity.external_id == external_id
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def get_by_user_and_provider(
        self,
        user_id: int,
        provider: OAuthProvider,
    ) -> Optional[OAuthIdentityDto]:
        stmt = select(OAuthIdentity).where(
            OAuthIdentity.user_id == user_id, OAuthIdentity.provider == provider
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def list_by_user(self, user_id: int) -> list[OAuthIdentityDto]:
        stmt = select(OAuthIdentity).where(OAuthIdentity.user_id == user_id)
        rows = await self.session.scalars(stmt)
        return [self._to_dto(row) for row in rows]

    async def delete_by_user_and_provider(self, user_id: int, provider: OAuthProvider) -> bool:
        stmt = delete(OAuthIdentity).where(
            OAuthIdentity.user_id == user_id,
            OAuthIdentity.provider == provider,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return cast(CursorResult, result).rowcount > 0


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: UserSession) -> SessionDto:
        return SessionDto.model_validate(row, from_attributes=True)

    def _active_clause(self) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
        now = datetime.now(timezone.utc)
        return (UserSession.revoked_at.is_(None), UserSession.expires_at > now)

    async def create(self, data: CreateSessionDto) -> SessionDto:
        now = datetime.now(timezone.utc)
        row = UserSession(
            user_id=data.user_id,
            refresh_token_hash=data.refresh_token_hash,
            ip_address=data.ip_address,
            user_agent=data.user_agent,
            last_used_at=now,
            expires_at=data.expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_dto(row)

    async def get_active_by_id(self, session_id: int) -> Optional[SessionDto]:
        stmt = select(UserSession).where(UserSession.id == session_id, *self._active_clause())
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def get_by_current_hash(self, refresh_token_hash: str) -> Optional[SessionDto]:
        stmt = select(UserSession).where(
            UserSession.refresh_token_hash == refresh_token_hash, *self._active_clause()
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def get_by_previous_hash_in_grace(self, refresh_token_hash: str) -> Optional[SessionDto]:
        now = datetime.now(timezone.utc)
        stmt = select(UserSession).where(
            UserSession.previous_refresh_token_hash == refresh_token_hash,
            UserSession.previous_hash_grace_until.is_not(None),
            UserSession.previous_hash_grace_until > now,
            *self._active_clause(),
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def get_rotatable_by_hash(self, refresh_token_hash: str) -> Optional[SessionDto]:
        current = await self.get_by_current_hash(refresh_token_hash)
        if current is not None:
            return current
        return await self.get_by_previous_hash_in_grace(refresh_token_hash)

    async def get_by_expired_previous_hash(self, refresh_token_hash: str) -> Optional[SessionDto]:
        # Distinguishes "this hash was the previous one, but its grace window
        # already elapsed" (theft) from "this hash was never issued at all"
        # (plain invalid token) -- get_by_current_hash/get_by_previous_hash_in_grace
        # intentionally can't tell these apart, since both simply fail to match.
        now = datetime.now(timezone.utc)
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
        row = await self.session.get(UserSession, session_id)
        assert row is not None
        now = datetime.now(timezone.utc)
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
            row.revoked_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def revoke_active_by_fingerprint(
        self, user_id: int, ip_address: str, user_agent: Optional[str]
    ) -> None:
        # Matches Telegram-style "logging in again from the same device
        # replaces the old session" -- login has no device id to key off of,
        # so ip_address + user_agent is the closest available fingerprint.
        now = datetime.now(timezone.utc)
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
                user_agent_clause,
                *self._active_clause(),
            )
            .values(revoked_at=now)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def revoke_all_by_user(self, user_id: int) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, *self._active_clause())
            .values(revoked_at=now)
        )
        await self.session.execute(stmt)
        await self.session.flush()
