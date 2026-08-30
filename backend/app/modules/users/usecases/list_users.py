from dataclasses import dataclass
from typing import Final, Optional

from app.core.enums import Role
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import DEFAULT_PAGE_SIZE, UserDto
from app.modules.users.repository import UserRepository

ALLOWED_ROLES: Final[list[Role]] = [Role.USER, Role.ADMIN, Role.OWNER]


@dataclass(frozen=True, kw_only=True)
class ListUsersInput:
    search: Optional[str] = None
    role: Optional[Role] = None
    is_blocked: Optional[bool] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class ListUsersUseCase(UseCase[ListUsersInput, tuple[list[UserDto], int]]):
    required_permission = Permission.USERS_VIEW

    def __init__(self, user_repository: UserRepository) -> None:
        self._user_repository = user_repository

    async def _execute(self, actor: UserDto, data: ListUsersInput) -> tuple[list[UserDto], int]:
        roles = [data.role] if data.role in ALLOWED_ROLES else ALLOWED_ROLES
        return await self._user_repository.list_filtered(
            roles=roles,
            search=data.search,
            is_blocked=data.is_blocked,
            page=data.page,
            page_size=data.page_size,
        )
