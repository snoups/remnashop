from collections.abc import Sequence
from typing import Optional, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user import User
from app.core.db.user_search import user_search_filter
from app.core.enums import Role
from app.modules.users.dto import DEFAULT_PAGE_SIZE, UserDto
from app.modules.users.filters import identity_filter


class UserBlacklistRepository:
    """Matches users against blacklisted identities: listing, blocking, unblocking."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dtos(self, rows: Sequence[User]) -> list[UserDto]:
        return [UserDto.model_validate(row, from_attributes=True) for row in rows]

    async def block_matching(self, telegram_ids: set[int], emails: set[str]) -> list[int]:
        if not telegram_ids and not emails:
            return []
        # Role.USER only: reconcile runs with no actor and no role guard, and an
        # auto-blocked OWNER has no recovery path (unblock_user needs a strictly
        # higher-role actor). Blocking staff stays an explicit BlockUserUseCase call.
        # emails come from normalize_identity (lowercased); User.email is stored as written.
        stmt = (
            select(User)
            .where(User.role == Role.USER)
            .where(User.is_blocked.is_(False))
            .where(identity_filter(telegram_ids, emails))
        )
        rows = list((await self.session.execute(stmt)).scalars())
        for row in rows:
            row.is_blocked = True
        await self.session.flush()
        return [row.id for row in rows]

    async def list_matching(
        self,
        telegram_ids: set[int],
        emails: set[str],
        *,
        roles: Sequence[Role],
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[UserDto], int]:
        if not telegram_ids and not emails:
            return [], 0
        filters = [User.role.in_(roles), identity_filter(telegram_ids, emails)]
        if search:
            filters.append(user_search_filter(search))

        total = await self.session.scalar(select(func.count()).select_from(User).where(*filters))
        stmt = (
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        return self._to_dtos(list(rows)), total or 0

    async def count_matching(
        self, telegram_ids: set[int], emails: set[str], *, roles: Sequence[Role]
    ) -> int:
        if not telegram_ids and not emails:
            return 0
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role.in_(roles), identity_filter(telegram_ids, emails))
        )
        return await self.session.scalar(stmt) or 0

    async def unblock_matching(
        self, telegram_ids: set[int], emails: set[str], *, roles: Sequence[Role]
    ) -> int:
        if not telegram_ids and not emails:
            return 0
        stmt = (
            update(User)
            .where(
                User.role.in_(roles),
                User.is_blocked.is_(True),
                identity_filter(telegram_ids, emails),
            )
            .values(is_blocked=False)
        )
        result = await self.session.execute(stmt)
        return cast(CursorResult, result).rowcount

    async def matching_identities(
        self, telegram_ids: set[int], emails: set[str], *, roles: Sequence[Role]
    ) -> tuple[set[int], set[str]]:
        if not telegram_ids and not emails:
            return set(), set()
        stmt = select(User.telegram_id, User.email).where(
            User.role.in_(roles), identity_filter(telegram_ids, emails)
        )
        rows = (await self.session.execute(stmt)).all()
        return (
            {tid for tid, _ in rows if tid in telegram_ids},
            {email.lower() for _, email in rows if email and email.lower() in emails},
        )
