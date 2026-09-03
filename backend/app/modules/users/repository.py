from typing import Callable, Optional

from loguru import logger
from sqlalchemy import ColumnElement, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.user import User
from app.core.enums import Role
from app.modules.users.dto import (
    DEFAULT_PAGE_SIZE,
    CreateUserDto,
    PromoteAdminDto,
    UpdateUserDto,
    UserDto,
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
        )

        self.session.add(db_user)
        await self.session.flush()

        dto = self._convert_to_dto(db_user)
        logger.debug(f"New user {dto.log} created in database")
        return dto

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

    async def exists_with_role(self, role: Role) -> bool:
        stmt = select(exists().where(User.role == role))
        return bool(await self.session.scalar(stmt))

    async def list_by_roles(self, roles: list[Role]) -> list[UserDto]:
        stmt = select(User).where(User.role.in_(roles)).order_by(User.created_at.desc())
        rows = (await self.session.scalars(stmt)).all()
        return self._convert_to_dto_list(list(rows))

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

    async def delete(self, user_id: int) -> bool:
        db_user = await self.session.get(User, user_id)

        if db_user is None:
            return False

        await self.session.delete(db_user)
        await self.session.flush()
        return True
