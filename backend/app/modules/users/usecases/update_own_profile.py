from dataclasses import dataclass
from typing import Optional

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.exceptions import ValidationError
from app.core.security import hash_password, verify_password
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UpdateUserDto, UserDto
from app.modules.users.repository import UserRepository


@dataclass(frozen=True, kw_only=True)
class UpdateOwnProfileDto:
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class UpdateOwnProfileUseCase(UseCase[UpdateOwnProfileDto, UserDto]):
    required_permission = Permission.OWN_ACCOUNT_MANAGE

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork, config: AppConfig) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._config = config

    async def _execute(self, actor: UserDto, data: UpdateOwnProfileDto) -> UserDto:
        password_hash = None

        if data.new_password is not None:
            pepper = self._config.crypt_key.get_secret_value()
            stored_hash = actor.password_hash

            if (
                stored_hash is None
                or data.current_password is None
                or not await verify_password(data.current_password, stored_hash, pepper)
            ):
                raise ValidationError("Current password is incorrect")

            password_hash = await hash_password(data.new_password, pepper)

        async with self._uow:
            updated = await self._user_repository.update_fields(
                actor.id, UpdateUserDto(name=data.name, password_hash=password_hash)
            )

        assert updated is not None
        return updated
