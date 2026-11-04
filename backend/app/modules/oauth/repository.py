from collections.abc import Iterable
from typing import Optional, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.errors import constraint_name
from app.core.db.filters import in_ids
from app.core.db.models.oauth_identity import OAuthIdentity
from app.core.enums import OAuthProvider
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError
from app.modules.oauth.dto import CreateOAuthIdentityDto, OAuthIdentityDto


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
            await self._flush_or_conflict()
            await self.session.refresh(existing)
            return self._to_dto(existing)

        row = OAuthIdentity(
            user_id=data.user_id,
            provider=data.provider,
            external_id=data.external_id,
            external_login=data.external_login,
        )
        self.session.add(row)
        await self._flush_or_conflict()
        return self._to_dto(row)

    async def _flush_or_conflict(self) -> None:
        # a concurrent connect of the same external account got past the pre-check
        try:
            await self.session.flush()
        except IntegrityError as error:
            if constraint_name(error) != "ux_oauth_identities_provider_external_id":
                raise
            raise ConflictError(
                "This account is already linked to another user",
                code=ErrorCode.OAUTH_ACCOUNT_LINKED_ELSEWHERE,
            ) from error

    async def find_by_provider_external_id(
        self,
        provider: OAuthProvider,
        external_id: str,
    ) -> Optional[OAuthIdentityDto]:
        stmt = select(OAuthIdentity).where(
            OAuthIdentity.provider == provider, OAuthIdentity.external_id == external_id
        )
        row = await self.session.scalar(stmt)
        return self._to_dto(row) if row else None

    async def list_by_user(self, user_id: int) -> list[OAuthIdentityDto]:
        stmt = select(OAuthIdentity).where(OAuthIdentity.user_id == user_id)
        rows = await self.session.scalars(stmt)
        return [self._to_dto(row) for row in rows]

    async def user_ids_with_identities(
        self, user_ids: list[int], providers: Iterable[OAuthProvider]
    ) -> set[int]:
        stmt = (
            select(OAuthIdentity.user_id)
            .where(
                in_ids(OAuthIdentity.user_id, user_ids),
                OAuthIdentity.provider.in_(list(providers)),
            )
            .distinct()
        )
        return set(await self.session.scalars(stmt))

    async def delete_by_user_and_provider(self, user_id: int, provider: OAuthProvider) -> bool:
        stmt = delete(OAuthIdentity).where(
            OAuthIdentity.user_id == user_id,
            OAuthIdentity.provider == provider,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return cast(CursorResult, result).rowcount > 0

    async def delete_all_by_user(self, user_id: int) -> int:
        result = await self.session.execute(
            delete(OAuthIdentity).where(OAuthIdentity.user_id == user_id)
        )
        await self.session.flush()
        return cast(CursorResult, result).rowcount

    async def delete_all_by_provider(self, provider: OAuthProvider) -> int:
        stmt = delete(OAuthIdentity).where(OAuthIdentity.provider == provider)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return cast(CursorResult, result).rowcount

    async def delete_all_oidc(self) -> int:
        return await self.delete_all_by_provider(OAuthProvider.OIDC)
