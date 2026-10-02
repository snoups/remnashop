import secrets
import string
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Final, Optional, cast

from loguru import logger
from sqlalchemy import ColumnElement, CursorResult, case, exists, func, or_, select, update
from sqlalchemy import delete as sa_delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.db.errors import constraint_name
from app.core.db.models.oauth_identity import OAuthIdentity
from app.core.db.models.user import User
from app.core.db.partial_update import apply_partial_update
from app.core.db.user_search import user_search_filter
from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.utils.time import datetime_now
from app.modules.users.dto import (
    DEFAULT_PAGE_SIZE,
    CreateUserDto,
    DeletedFilter,
    PromoteAdminDto,
    UpdateUserDto,
    UserDto,
    UserListItemDto,
    UserSort,
)
from app.modules.users.filters import ACTIVE_SUBSCRIPTIONS, identity_filter

_REFERRAL_CODE_ALPHABET: Final[str] = string.ascii_uppercase + string.digits
_REFERRAL_CODE_LENGTH: Final[int] = 8
_REFERRAL_CODE_MAX_ATTEMPTS: Final[int] = 5

_DISCOUNT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "personal_discount",
        "personal_discount_promocode_id",
        "purchase_discount",
        "purchase_discount_promocode_id",
    }
)
_UNIQUE_VIOLATIONS: Final[dict[str, tuple[str, ErrorCode]]] = {
    "ux_users_single_owner": ("Owner already exists", ErrorCode.OWNER_ALREADY_EXISTS),
    "ix_users_login": ("Login already taken", ErrorCode.LOGIN_TAKEN),
    "ix_users_telegram_id": ("Telegram account already registered", ErrorCode.TELEGRAM_ID_TAKEN),
}


_SORT_COLUMNS: Final[dict[str, InstrumentedAttribute[Any] | ColumnElement[Any]]] = {
    "created_at": User.created_at,
    "points": User.points,
    "discount": User.personal_discount,
    "name": func.lower(User.name),
    # groups by channel type -- a count would tie nearly everyone at one channel
    "channels": case((User.telegram_id.is_not(None), 4), else_=0)
    + case((User.email.is_not(None), 2), else_=0)
    + case((User.login.is_not(None), 1), else_=0),
    "subscriptions": ACTIVE_SUBSCRIPTIONS,
}


def _discount_filter() -> ColumnElement[bool]:
    return or_(User.personal_discount > 0, User.purchase_discount > 0)


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
        await self._flush_unique()

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

    async def _flush_unique(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as error:
            violation = _UNIQUE_VIOLATIONS.get(constraint_name(error) or "")
            if violation is None:
                raise
            message, code = violation
            raise ConflictError(message, code=code) from error

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
            raise ValidationError(
                f"Adjustment would take user '{user_id}' points below zero",
                code=ErrorCode.POINTS_BELOW_ZERO,
            )

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

    async def spend_purchase_discount(self, user_id: int, percent: int) -> bool:
        # Atomic claim, like spend_trial: of two checkouts quoted against the
        # same one-shot discount only one sees rowcount 1.
        stmt = (
            update(User)
            .where(User.id == user_id, User.purchase_discount == percent)
            .values(purchase_discount=0, purchase_discount_promocode_id=None)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return cast(CursorResult, result).rowcount == 1

    async def restore_purchase_discount(
        self, user_id: int, percent: int, promocode_id: Optional[int]
    ) -> None:
        # only into an empty slot -- never over a discount granted since
        await self.session.execute(
            update(User)
            .where(User.id == user_id, User.purchase_discount == 0)
            .values(purchase_discount=percent, purchase_discount_promocode_id=promocode_id)
        )
        await self.session.flush()

    async def exists_with_role(self, role: Role) -> bool:
        stmt = select(exists().where(User.role == role))
        return bool(await self.session.scalar(stmt))

    async def list_by_roles(self, roles: Sequence[Role]) -> list[UserDto]:
        stmt = select(User).where(User.role.in_(roles)).order_by(User.created_at.desc())
        rows = (await self.session.scalars(stmt)).all()
        return self._convert_to_dto_list(list(rows))

    async def list_by_ids(self, user_ids: list[int]) -> list[UserDto]:
        if not user_ids:
            return []
        result = await self.session.execute(select(User).where(User.id.in_(user_ids)))
        return self._convert_to_dto_list(list(result.scalars()))

    async def get_list_item(self, user_id: int, roles: Sequence[Role]) -> UserListItemDto:
        row = (
            await self.session.execute(
                select(User, ACTIVE_SUBSCRIPTIONS).where(User.id == user_id, User.role.in_(roles))
            )
        ).first()
        if row is None:
            raise NotFoundError(f"User '{user_id}' not found", code=ErrorCode.USER_NOT_FOUND)
        user, count = row
        return UserListItemDto.model_validate(user, from_attributes=True).model_copy(
            update={"active_subscriptions": count}
        )

    async def list_filtered(
        self,
        *,
        roles: Sequence[Role],
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
            filters.append(User.created_at < created_to)
        for condition, wanted in (
            (User.is_blocked.is_(True), is_blocked),
            (_discount_filter(), has_discount),
            (ACTIVE_SUBSCRIPTIONS > 0, has_subscription),
            (User.is_trial_available.is_(True), is_trial_available),
        ):
            if wanted is not None:
                filters.append(condition if wanted else ~condition)
        if identities is not None:
            if not any(identities):
                return [], 0
            filters.append(identity_filter(*identities))

        count_stmt = select(func.count()).select_from(User).where(*filters)
        total = await self.session.scalar(count_stmt)

        sort_col = _SORT_COLUMNS[sort]
        stmt = (
            select(User, ACTIVE_SUBSCRIPTIONS)
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
            raise NotFoundError(f"User '{user_id}' not found", code=ErrorCode.USER_NOT_FOUND)
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

        apply_partial_update(db_user, data, skip=_DISCOUNT_FIELDS)
        # each promocode id is written with its discount, None included
        if data.personal_discount is not None:
            db_user.personal_discount = data.personal_discount
            db_user.personal_discount_promocode_id = data.personal_discount_promocode_id
        if data.purchase_discount is not None:
            db_user.purchase_discount = data.purchase_discount
            db_user.purchase_discount_promocode_id = data.purchase_discount_promocode_id

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

        await self._flush_unique()
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

    async def unblock_all(self) -> int:
        stmt = update(User).where(User.is_blocked.is_(True)).values(is_blocked=False)
        result = await self.session.execute(stmt)
        return cast(CursorResult, result).rowcount

    async def anonymize(self, user_id: int) -> Optional[UserDto]:
        # Soft delete: transactions, subscriptions and referrals keep pointing at
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
