from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.users.dto import SetUserPersonalDiscountDto, UpdateUserDto, UserDto
from app.modules.users.repository import UserRepository


class SetUserPersonalDiscountUseCase(UseCase[SetUserPersonalDiscountDto, UserDto]):
    required_permission = Permission.USERS_DISCOUNT_MANAGE

    def __init__(self, user_repository: UserRepository, uow: UnitOfWork) -> None:
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: SetUserPersonalDiscountDto) -> UserDto:
        async with self._uow:
            if not 0 <= data.percent <= 100:
                raise ValidationError("percent must be between 0 and 100")

            target = await self._user_repository.get_by_id(data.user_id)
            if target is None:
                raise NotFoundError(f"User '{data.user_id}' not found")
            if target.role in (Role.ADMIN, Role.OWNER) and not PermissionPolicy.has_permission(
                actor, Permission.ADMINS_MANAGE
            ):
                raise ValidationError("Cannot set a personal discount on a staff account")

        async with self._uow:
            updated = await self._user_repository.update_fields(
                data.user_id, UpdateUserDto(personal_discount=data.percent)
            )
        if updated is None:
            raise NotFoundError(f"User '{data.user_id}' not found")
        return updated
