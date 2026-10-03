from typing import Optional

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.users.dto import SetUserDiscountDto, UpdateUserDto, UserDto
from app.modules.users.events import (
    UserPersonalDiscountChangedEvent,
    UserPurchaseDiscountChangedEvent,
)
from app.modules.users.repository import UserRepository


def _changed(new: Optional[int], old: int) -> bool:
    return new is not None and new != old


class SetUserDiscountUseCase(UseCase[SetUserDiscountDto, UserDto]):
    required_permission = Permission.USERS_DISCOUNT_MANAGE

    def __init__(
        self, user_repository: UserRepository, uow: UnitOfWork, event_publisher: EventPublisher
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: SetUserDiscountDto) -> UserDto:
        for percent in (data.personal_discount, data.purchase_discount):
            if percent is not None and not 0 <= percent <= 100:
                raise ValidationError(
                    "percent must be between 0 and 100", code=ErrorCode.DISCOUNT_PERCENT_INVALID
                )

        async with self._uow:
            target = await self._user_repository.get_by_id(data.user_id)
            if target is None:
                raise NotFoundError(
                    f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                )
            if target.role in (Role.ADMIN, Role.OWNER) and not PermissionPolicy.has_permission(
                actor, Permission.ADMINS_MANAGE
            ):
                raise ValidationError(
                    "Cannot set a discount on a staff account",
                    code=ErrorCode.DISCOUNT_STAFF_ACCOUNT,
                )

            personal_changed = _changed(data.personal_discount, target.personal_discount)
            purchase_changed = _changed(data.purchase_discount, target.purchase_discount)
            if not (personal_changed or purchase_changed):
                return target

            # a manual value clears the promocode the old one came from
            updated = await self._user_repository.update_fields(
                data.user_id,
                UpdateUserDto(
                    personal_discount=data.personal_discount if personal_changed else None,
                    purchase_discount=data.purchase_discount if purchase_changed else None,
                ),
            )
            if updated is None:
                raise NotFoundError(
                    f"User '{data.user_id}' not found", code=ErrorCode.USER_NOT_FOUND
                )

            if personal_changed:
                await self._event_publisher.publish(
                    UserPersonalDiscountChangedEvent(
                        actor=actor,
                        target=target,
                        old_percent=target.personal_discount,
                        new_percent=updated.personal_discount,
                    )
                )
            if purchase_changed:
                await self._event_publisher.publish(
                    UserPurchaseDiscountChangedEvent(
                        actor=actor,
                        target=target,
                        old_percent=target.purchase_discount,
                        new_percent=updated.purchase_discount,
                    )
                )

        logger.info(
            f"{actor.log} Set discounts of user '{data.user_id}': "
            f"personal={updated.personal_discount}, purchase={updated.purchase_discount}"
        )
        return updated
