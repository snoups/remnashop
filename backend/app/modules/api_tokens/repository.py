from datetime import timedelta
from typing import Final, Optional

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.api_token import ApiToken
from app.core.utils.time import datetime_now
from app.modules.api_tokens.dto import ApiTokenDto, CreateApiTokenDto

_TOUCH_INTERVAL: Final[timedelta] = timedelta(minutes=1)


class ApiTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: ApiToken) -> ApiTokenDto:
        return ApiTokenDto.model_validate(row, from_attributes=True)

    async def create(self, data: CreateApiTokenDto) -> ApiTokenDto:
        row = ApiToken(
            name=data.name,
            token_hash=data.token_hash,
            scopes=data.scopes,
            ip_allowlist=data.ip_allowlist,
            created_by_user_id=data.created_by_user_id,
            expires_at=data.expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_dto(row)

    async def find_active_by_hash(self, token_hash: str) -> Optional[ApiTokenDto]:
        now = datetime_now()
        stmt = select(ApiToken).where(
            ApiToken.token_hash == token_hash,
            ApiToken.revoked_at.is_(None),
            or_(ApiToken.expires_at.is_(None), ApiToken.expires_at > now),
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def touch_last_used(self, token_id: int) -> None:
        # at most once a window: a polling integration would otherwise rewrite
        # the row on every request
        now = datetime_now()
        await self.session.execute(
            update(ApiToken)
            .where(
                ApiToken.id == token_id,
                or_(
                    ApiToken.last_used_at.is_(None),
                    ApiToken.last_used_at < now - _TOUCH_INTERVAL,
                ),
            )
            .values(last_used_at=now)
            .execution_options(synchronize_session="fetch")
        )

    # expired tokens stay listed (shown as expired) until revoked
    async def list_not_revoked(self) -> list[ApiTokenDto]:
        stmt = (
            select(ApiToken)
            .where(ApiToken.revoked_at.is_(None))
            .order_by(ApiToken.created_at.desc())
        )
        rows = await self.session.scalars(stmt)
        return [self._to_dto(row) for row in rows]

    async def revoke_by_id(self, token_id: int) -> Optional[ApiTokenDto]:
        # session.get() may return an identity-mapped row with expired
        # attributes, and reading revoked_at off it raises MissingGreenlet;
        # a SELECT always loads them
        stmt = select(ApiToken).where(ApiToken.id == token_id, ApiToken.revoked_at.is_(None))
        row = await self.session.scalar(stmt)
        if row is None:
            return None
        row.revoked_at = datetime_now()
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)
