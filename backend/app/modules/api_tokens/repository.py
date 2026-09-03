from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.api_token import ApiToken
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import ApiTokenDto, CreateApiTokenDto


class ApiTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: ApiToken) -> ApiTokenDto:
        return ApiTokenDto(
            id=row.id,
            name=row.name,
            permissions=[Permission(p) for p in row.permissions if p in Permission],
            created_by_user_id=row.created_by_user_id,
            last_used_at=row.last_used_at,
            revoked_at=row.revoked_at,
            expires_at=row.expires_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def create(self, data: CreateApiTokenDto) -> ApiTokenDto:
        row = ApiToken(
            name=data.name,
            token_hash=data.token_hash,
            permissions=[p.value for p in data.permissions],
            created_by_user_id=data.created_by_user_id,
            expires_at=data.expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_dto(row)

    async def get_active_by_hash(self, token_hash: str) -> Optional[ApiTokenDto]:
        now = datetime.now(timezone.utc)
        stmt = select(ApiToken).where(
            ApiToken.token_hash == token_hash,
            ApiToken.revoked_at.is_(None),
            or_(ApiToken.expires_at.is_(None), ApiToken.expires_at > now),
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def touch_last_used(self, token_id: int) -> None:
        row = await self.session.get(ApiToken, token_id)
        if row is not None:
            row.last_used_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def list_active(self) -> list[ApiTokenDto]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(ApiToken)
            .where(
                ApiToken.revoked_at.is_(None),
                or_(ApiToken.expires_at.is_(None), ApiToken.expires_at > now),
            )
            .order_by(ApiToken.created_at.desc())
        )
        rows = await self.session.scalars(stmt)
        return [self._to_dto(row) for row in rows]

    async def revoke_by_id(self, token_id: int) -> Optional[ApiTokenDto]:
        # A plain session.get() can return an identity-mapped instance with
        # expired (unloaded) attributes -- reading row.revoked_at on that
        # outside an explicit refresh raises MissingGreenlet. A SELECT always
        # populates the returned instance's attributes from the query result.
        stmt = select(ApiToken).where(ApiToken.id == token_id, ApiToken.revoked_at.is_(None))
        row = await self.session.scalar(stmt)
        if row is None:
            return None
        row.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)
