import secrets
import string
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Final, Optional, cast

from loguru import logger
from sqlalchemy import (
    ARRAY,
    BigInteger,
    ColumnElement,
    CursorResult,
    Text,
    any_,
    case,
    exists,
    false,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.db.models.oauth_identity import OAuthIdentity
from app.core.db.models.subscription import Subscription
from app.core.db.models.user import User
from app.core.db.user_search import user_search_filter
from app.core.enums import Locale, Role, SubscriptionStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.users.dto import (
    DEFAULT_PAGE_SIZE,
    CreateUserDto,
    DeletedFilter,
    PromoteAdminDto,
    UpdateUserDto,
    UserDto,
    UserListItemDto,
    UserListStatsDto,
    UserSort,
)

_REFERRAL_CODE_ALPHABET: Final[str] = string.ascii_uppercase + string.digits
_REFERRAL_CODE_LENGTH: Final[int] = 8
_REFERRAL_CODE_MAX_ATTEMPTS: Final[int] = 5


# asyncpg caps a statement at 32,767 bind parameters; stay well under that so a
# large bulk-block batch still fits after other predicates are added.
_MAX_IN_PARAMS: Final[int] = 20_000

_ACTIVE_SUBSCRIPTIONS: Final[ColumnElement[int]] = (
    select(func.count())
    .where(Subscription.user_id == User.id, Subscription.status == SubscriptionStatus.ACTIVE)
    .correlate(User)
    .scalar_subquery()
)

_SORT_COLUMNS: Final[dict[str, InstrumentedAttribute[Any] | ColumnElement[Any]]] = {
    "created_at": User.created_at,
    "points": User.points,
    "discount": User.personal_discount,
    "name": func.lower(User.name),
    # groups by channel type -- a count would tie nearly everyone at one channel
    "channels": case((User.telegram_id.is_not(None), 4), else_=0)
    + case((User.email.is_not(None), 2), else_=0)
    + case((User.login.is_not(None), 1), else_=0),
    "subscriptions": _ACTIVE_SUBSCRIPTIONS,
}


def _discount_filter() -> ColumnElement[bool]:
    return or_(User.personal_discount > 0, User.purchase_discount > 0)


def _identity_filter(telegram_ids: set[int], emails: set[str]) -> ColumnElement[bool]:
    # one array bind each instead of IN (...) -- a blacklist source can exceed
    # asyncpg's 32,767 bind-parameter cap. emails are expected lowercased.
    return or_(
        User.telegram_id == any_(literal(list(telegram_ids), ARRAY(BigInteger)))
        if telegram_ids
        else false(),
        func.lower(User.email) == any_(literal(list(emails), ARRAY(Text))) if emails else false(),
    )


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

        self._convert_to_dto: Callable[[User], UserDto] = lambda row: UserDto.model_validate(
            row, from_attributes=True
        )
        self._convert_to_dto_list: Callable[[list[User]], list[UserDto]] = lambda rows: [
            UserDto.model_validate(row, from_attributes=True) for row in rows
        ]

    async def create(self, data: CreateUserDto) -> UserDto:
        db_user = User(
            name=data.name,
            role=data.role,
            language=data.language,
            is_blocked=data.is_blocked,
            telegram_id=data.telegram_id,
            username=data.username,
            email=data.email,
            login=data.login,
            password_hash=data.password_hash,
            permission_grants=data.permission_grants,
            permission_revokes=data.permission_revokes,
            ip_allowlist=data.ip_allowlist,
            referral_code=await self._generate_referral_code(),
            points=Decimal(0),
        )

        self.session.add(db_user)
        await self.session.flush()

        dto = self._convert_to_dto(db_user)
        logger.debug(f"New user {dto.log} created in database")
        return dto

    async def _generate_referral_code(self) -> str:
        # Check-then-use, not atomic against a concurrent insert of the same
        # code -- same accepted tradeoff as GeneratePromocodeCodeUseCase.
        # 36^8 candidates makes a real collision astronomically unlikely.
        for _ in range(_REFERRAL_CODE_MAX_ATTEMPTS):
            code = "".join(
                secrets.choice(_REFERRAL_CODE_ALPHABET) for _ in range(_REFERRAL_CODE_LENGTH)
            )
            if await self.get_by_referral_code(code) is None:
                return code
        raise RuntimeError("Could not generate a unique referral code")

    async def get_by_id(self, user_id: int) -> Optional[UserDto]:
        stmt = select(User).where(User.id == user_id)
        db_user = await self.session.scalar(stmt)
        if db_user is None:
            logger.debug(f"User id='{user_id}' not found")
            return None
        return self._convert_to_dto(db_user)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[UserDto]:
        stmt = select(User).where(User.telegram_id == telegram_id)
        db_user = await self.session.scalar(stmt)
        return self._convert_to_dto(db_user) if db_user else None

    async def list_by_telegram_ids(self, telegram_ids: list[int]) -> list[UserDto]:
        if not telegram_ids:
            return []
        users: list[UserDto] = []
        for start in range(0, len(telegram_ids), _MAX_IN_PARAMS):
            chunk = telegram_ids[start : start + _MAX_IN_PARAMS]
            stmt = select(User).where(User.telegram_id.in_(chunk))
            users.extend(self._convert_to_dto(row) for row in (await self.session.scalars(stmt)))
        return users

    async def get_by_email(self, email: str) -> Optional[UserDto]:
        stmt = select(User).where(User.email == email)
        db_user = await self.session.scalar(stmt)
        return self._convert_to_dto(db_user) if db_user else None

    async def get_by_login(self, login: str) -> Optional[UserDto]:
        stmt = select(User).where(User.login == login)
        db_user = await self.session.scalar(stmt)
        return self._convert_to_dto(db_user) if db_user else None

    async def get_by_username(self, username: str) -> Optional[UserDto]:
        stmt = select(User).where(User.username == username)
        db_user = await self.session.scalar(stmt)
        return self._convert_to_dto(db_user) if db_user else None

    async def get_by_referral_code(self, code: str) -> Optional[UserDto]:
        stmt = select(User).where(User.referral_code == code)
        db_user = await self.session.scalar(stmt)
        return self._convert_to_dto(db_user) if db_user else None

    async def credit_points(self, user_id: int, amount: Decimal) -> None:
        # Atomic UPDATE, not read-modify-write -- concurrent grants (two
        # referral rewards landing at once) can't clobber each other. The
        # non-negative floor is part of the same predicate for the same
        # reason: a caller checking `points + delta >= 0` first and updating
        # after would let two concurrent debits both pass and overdraw.
        stmt = (
            update(User)
            .where(User.id == user_id, User.points + amount >= 0)
            .values(points=User.points + amount)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        if cast(CursorResult, result).rowcount == 0:
            raise ValidationError(f"Adjustment would take user '{user_id}' points below zero")

    async def spend_trial(self, user_id: int) -> bool:
        # Atomic claim: of two concurrent callers only one sees rowcount 1.
        stmt = (
            update(User)
            .where(User.id == user_id, User.is_trial_available.is_(True))
            .values(is_trial_available=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return cast(CursorResult, result).rowcount == 1

    async def exists_with_role(self, role: Role) -> bool:
        stmt = select(exists().where(User.role == role))
        return bool(await self.session.scalar(stmt))

    async def list_by_roles(self, roles: list[Role]) -> list[UserDto]:
        stmt = select(User).where(User.role.in_(roles)).order_by(User.created_at.desc())
        rows = (await self.session.scalars(stmt)).all()
        return self._convert_to_dto_list(list(rows))

    async def list_by_ids(self, user_ids: list[int]) -> list[UserDto]:
        if not user_ids:
            return []
        result = await self.session.execute(select(User).where(User.id.in_(user_ids)))
        return self._convert_to_dto_list(list(result.scalars()))

    async def list_filtered(
        self,
        *,
        roles: list[Role],
        search: Optional[str] = None,
        is_blocked: Optional[bool] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        has_discount: Optional[bool] = None,
        has_subscription: Optional[bool] = None,
        is_trial_available: Optional[bool] = None,
        # (telegram_ids, emails) a user must match one of
        identities: Optional[tuple[set[int], set[str]]] = None,
        deleted: DeletedFilter = "exclude",
        sort: UserSort = "created_at",
        descending: bool = True,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[UserListItemDto], int]:
        filters: list[ColumnElement[bool]] = [User.role.in_(roles)]
        if deleted == "exclude":
            filters.append(User.deleted_at.is_(None))
        elif deleted == "only":
            filters.append(User.deleted_at.is_not(None))
        if search:
            filters.append(user_search_filter(search))
        if created_from is not None:
            filters.append(User.created_at >= created_from)
        if created_to is not None:
            filters.append(User.created_at <= created_to)
        for condition, wanted in (
            (User.is_blocked.is_(True), is_blocked),
            (_discount_filter(), has_discount),
            (_ACTIVE_SUBSCRIPTIONS > 0, has_subscription),
            (User.is_trial_available.is_(True), is_trial_available),
        ):
            if wanted is not None:
                filters.append(condition if wanted else ~condition)
        if identities is not None:
            if not any(identities):
                return [], 0
            filters.append(_identity_filter(*identities))

        count_stmt = select(func.count()).select_from(User).where(*filters)
        total = await self.session.scalar(count_stmt)

        sort_col = _SORT_COLUMNS[sort]
        stmt = (
            select(User, _ACTIVE_SUBSCRIPTIONS)
            .where(*filters)
            # ties by registration date (imported users' ids don't follow it),
            # then id to keep offset pages stable
            .order_by(
                sort_col.desc() if descending else sort_col.asc(),
                User.created_at.desc(),
                User.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(stmt)).all()

        items = [
            UserListItemDto.model_validate(user, from_attributes=True).model_copy(
                update={"active_subscriptions": count}
            )
            for user, count in rows
        ]
        return items, int(total or 0)

    async def update_telegram_profile(
        self, user_id: int, *, name: str, username: Optional[str], language: Locale
    ) -> UserDto:
        db_user = await self.session.get(User, user_id)
        if db_user is None:
            raise NotFoundError(f"User '{user_id}' not found")
        db_user.name = name
        db_user.username = username
        db_user.language = language
        await self.session.flush()
        await self.session.refresh(db_user)
        return self._convert_to_dto(db_user)

    async def update_fields(self, user_id: int, data: UpdateUserDto) -> Optional[UserDto]:
        db_user = await self.session.get(User, user_id)

        if db_user is None:
            return None

        if data.name is not None:
            db_user.name = data.name
        if data.password_hash is not None:
            db_user.password_hash = data.password_hash
        if data.permission_grants is not None:
            db_user.permission_grants = data.permission_grants
        if data.permission_revokes is not None:
            db_user.permission_revokes = data.permission_revokes
        if data.ip_allowlist is not None:
            db_user.ip_allowlist = data.ip_allowlist
        if data.personal_discount is not None:
            db_user.personal_discount = data.personal_discount
            db_user.personal_discount_promocode_id = data.personal_discount_promocode_id
        if data.purchase_discount is not None:
            db_user.purchase_discount = data.purchase_discount
            db_user.purchase_discount_promocode_id = data.purchase_discount_promocode_id
        if data.is_trial_available is not None:
            db_user.is_trial_available = data.is_trial_available

        await self.session.flush()
        # updated_at is server-computed via onupdate=; refresh so the DTO
        # conversion below doesn't lazy-load it outside of an awaited call.
        await self.session.refresh(db_user)
        return self._convert_to_dto(db_user)

    async def promote_to_admin(self, user_id: int, data: PromoteAdminDto) -> Optional[UserDto]:
        db_user = await self.session.get(User, user_id)

        if db_user is None:
            return None

        db_user.role = Role.ADMIN
        db_user.login = data.login
        db_user.password_hash = data.password_hash
        db_user.permission_grants = data.permission_grants
        db_user.permission_revokes = data.permission_revokes

        await self.session.flush()
        await self.session.refresh(db_user)
        return self._convert_to_dto(db_user)

    async def demote_from_admin(self, user_id: int) -> Optional[UserDto]:
        db_user = await self.session.get(User, user_id)

        if db_user is None:
            return None

        db_user.role = Role.USER
        db_user.login = None
        db_user.password_hash = None
        db_user.permission_grants = None
        db_user.permission_revokes = None
        db_user.ip_allowlist = None

        await self.session.flush()
        await self.session.refresh(db_user)
        return self._convert_to_dto(db_user)

    async def set_blocked(self, user_id: int, is_blocked: bool) -> Optional[UserDto]:
        db_user = await self.session.get(User, user_id)
        if db_user is None:
            return None
        db_user.is_blocked = is_blocked
        await self.session.flush()
        await self.session.refresh(db_user)
        return self._convert_to_dto(db_user)

    async def reset_referral_code(self, user_id: int) -> Optional[UserDto]:
        db_user = await self.session.get(User, user_id)
        if db_user is None:
            return None
        db_user.referral_code = await self._generate_referral_code()
        await self.session.flush()
        await self.session.refresh(db_user)
        return self._convert_to_dto(db_user)

    async def set_notifications_seen_at(self, user_id: int, seen_at: datetime) -> None:
        db_user = await self.session.get(User, user_id)
        if db_user is None:
            return
        db_user.notifications_seen_at = seen_at
        await self.session.flush()

    async def set_notification_groups(self, user_id: int, groups: list[str]) -> None:
        db_user = await self.session.get(User, user_id)
        if db_user is None:
            return
        db_user.notification_groups = groups
        await self.session.flush()

    async def bulk_block_by_telegram_ids(self, telegram_ids: list[int]) -> list[int]:
        if not telegram_ids:
            return []
        stmt = (
            select(User).where(User.telegram_id.in_(telegram_ids)).where(User.is_blocked.is_(False))
        )
        rows = list((await self.session.execute(stmt)).scalars())
        for row in rows:
            row.is_blocked = True
        await self.session.flush()
        return [row.id for row in rows]

    async def unblock_all(self) -> int:
        stmt = update(User).where(User.is_blocked.is_(True)).values(is_blocked=False)
        result = await self.session.execute(stmt)
        return cast(CursorResult, result).rowcount

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
            .where(_identity_filter(telegram_ids, emails))
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
        roles: list[Role],
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[UserDto], int]:
        if not telegram_ids and not emails:
            return [], 0
        filters = [User.role.in_(roles), _identity_filter(telegram_ids, emails)]
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
        return self._convert_to_dto_list(list(rows)), total or 0

    async def count_matching(
        self, telegram_ids: set[int], emails: set[str], *, roles: list[Role]
    ) -> int:
        if not telegram_ids and not emails:
            return 0
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role.in_(roles), _identity_filter(telegram_ids, emails))
        )
        return await self.session.scalar(stmt) or 0

    async def unblock_matching(
        self, telegram_ids: set[int], emails: set[str], *, roles: list[Role]
    ) -> int:
        if not telegram_ids and not emails:
            return 0
        stmt = (
            update(User)
            .where(
                User.role.in_(roles),
                User.is_blocked.is_(True),
                _identity_filter(telegram_ids, emails),
            )
            .values(is_blocked=False)
        )
        result = await self.session.execute(stmt)
        return cast(CursorResult, result).rowcount

    async def matching_identities(
        self, telegram_ids: set[int], emails: set[str], *, roles: list[Role]
    ) -> tuple[set[int], set[str]]:
        if not telegram_ids and not emails:
            return set(), set()
        stmt = select(User.telegram_id, User.email).where(
            User.role.in_(roles), _identity_filter(telegram_ids, emails)
        )
        rows = (await self.session.execute(stmt)).all()
        return (
            {tid for tid, _ in rows if tid in telegram_ids},
            {email.lower() for _, email in rows if email and email.lower() in emails},
        )

    async def anonymize(self, user_id: int) -> Optional[UserDto]:
        # Soft delete: payments, subscriptions and referrals keep pointing at
        # this row, so revenue and referral history survive. What identifies
        # the person goes; the unique columns are freed for a new sign-up.
        db_user = await self.session.get(User, user_id)
        if db_user is None:
            return None
        db_user.name = ""
        db_user.username = None
        db_user.telegram_id = None
        db_user.email = None
        db_user.login = None
        db_user.password_hash = None
        db_user.referral_code = None
        db_user.personal_discount = 0
        db_user.purchase_discount = 0
        db_user.personal_discount_promocode_id = None
        db_user.purchase_discount_promocode_id = None
        db_user.points = Decimal(0)
        db_user.permission_grants = None
        db_user.permission_revokes = None
        db_user.ip_allowlist = None
        db_user.notification_groups = None
        db_user.deleted_at = datetime_now()
        # provider subject ids are personal data too; nothing else reads them
        await self.session.execute(sa_delete(OAuthIdentity).where(OAuthIdentity.user_id == user_id))
        await self.session.flush()
        await self.session.refresh(db_user)
        return self._convert_to_dto(db_user)

    async def delete(self, user_id: int) -> bool:
        db_user = await self.session.get(User, user_id)

        if db_user is None:
            return False

        await self.session.delete(db_user)
        await self.session.flush()
        return True

    async def list_stats(
        self,
        *,
        roles: list[Role],
        new_since: datetime,
        previous_since: datetime,
        growth_since: datetime,
    ) -> UserListStatsDto:
        row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(User.created_at >= new_since),
                    func.count().filter(_ACTIVE_SUBSCRIPTIONS > 0),
                    func.count().filter(User.is_blocked.is_(True)),
                    func.count().filter(
                        User.created_at >= previous_since, User.created_at < new_since
                    ),
                    func.count().filter(User.created_at >= growth_since),
                ).where(User.role.in_(roles), User.deleted_at.is_(None))
            )
        ).one()
        return UserListStatsDto(
            total=row[0],
            new=row[1],
            subscribed=row[2],
            blocked=row[3],
            new_previous=row[4],
            total_growth=row[5],
        )

    async def count_by_role(self, role: Role) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).where(User.role == role, User.deleted_at.is_(None))
            )
            or 0
        )

    async def count_new_since(self, cutoff: datetime, role: Role) -> int:
        return int(
            await self.session.scalar(
                select(func.count()).where(User.role == role, User.created_at >= cutoff)
            )
            or 0
        )

    async def earliest_registration(self, role: Role) -> Optional[date]:
        earliest = await self.session.scalar(
            select(func.min(func.date(func.timezone("UTC", User.created_at)))).where(
                User.role == role
            )
        )
        return cast(Optional[date], earliest)

    async def count_registrations_by_day(
        self, since: datetime, role: Role
    ) -> list[tuple[date, int]]:
        day_col = func.date(func.timezone("UTC", User.created_at))
        stmt = (
            select(day_col, func.count())
            .where(User.role == role, User.created_at >= since)
            .group_by(day_col)
            .order_by(day_col)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return list(rows.all())

    async def list_ids_registered_since(self, since: datetime, role: Role) -> list[int]:
        result = await self.session.execute(
            select(User.id).where(User.role == role, User.created_at >= since)
        )
        return list(result.scalars().all())

    async def list_id_and_registration_date_since(
        self, since: datetime, role: Role
    ) -> list[tuple[int, date]]:
        day_col = func.date(func.timezone("UTC", User.created_at))
        result = await self.session.execute(
            select(User.id, day_col).where(User.role == role, User.created_at >= since)
        )
        return list(result.tuples().all())
