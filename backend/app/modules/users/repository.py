import secrets
import string
from decimal import Decimal
from typing import Callable, Final, Optional, cast

from loguru import logger
from sqlalchemy import ColumnElement, CursorResult, exists, false, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user import User
from app.core.enums import Role
from app.core.exceptions import ValidationError
from app.modules.users.dto import (
    DEFAULT_PAGE_SIZE,
    CreateUserDto,
    PromoteAdminDto,
    UpdateUserDto,
    UserDto,
)

_REFERRAL_CODE_ALPHABET: Final[str] = string.ascii_uppercase + string.digits
_REFERRAL_CODE_LENGTH: Final[int] = 8
_REFERRAL_CODE_MAX_ATTEMPTS: Final[int] = 5


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
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[UserDto], int]:
        filters: list[ColumnElement[bool]] = [User.role.in_(roles)]
        if search:
            pattern = f"%{search}%"
            search_filters: list[ColumnElement[bool]] = [
                User.name.ilike(pattern),
                User.login.ilike(pattern),
                User.username.ilike(pattern),
                User.email.ilike(pattern),
            ]
            # telegram_id is a BigInteger column -- a longer digit string is
            # a valid `search` value but out of range for the DB type, and
            # would otherwise raise NumericValueOutOfRange from asyncpg.
            if search.isdigit() and int(search).bit_length() < 63:
                search_filters.append(User.telegram_id == int(search))
            filters.append(or_(*search_filters))
        if is_blocked is not None:
            filters.append(User.is_blocked == is_blocked)

        count_stmt = select(func.count()).select_from(User).where(*filters)
        total = await self.session.scalar(count_stmt)

        stmt = (
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()

        return self._convert_to_dto_list(list(rows)), int(total or 0)

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
        if data.purchase_discount is not None:
            db_user.purchase_discount = data.purchase_discount
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
            .where(
                or_(
                    User.telegram_id.in_(telegram_ids) if telegram_ids else false(),
                    func.lower(User.email).in_(emails) if emails else false(),
                )
            )
        )
        rows = list((await self.session.execute(stmt)).scalars())
        for row in rows:
            row.is_blocked = True
        await self.session.flush()
        return [row.id for row in rows]

    async def delete(self, user_id: int) -> bool:
        db_user = await self.session.get(User, user_id)

        if db_user is None:
            return False

        await self.session.delete(db_user)
        await self.session.flush()
        return True
