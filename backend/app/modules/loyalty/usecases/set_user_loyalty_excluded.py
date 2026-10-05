from functools import partial

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission, PermissionPolicy
from app.core.usecase import UseCase
from app.modules.loyalty.dispatch import LoyaltyRecalcDispatch
from app.modules.loyalty.dto import SetUserLoyaltyExcludedDto, UserLoyaltyDto
from app.modules.loyalty.events import UserLoyaltyExclusionChangedEvent
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.usecases.get_user_loyalty import build_user_loyalty
from app.modules.pricing import PricingRepository
from app.modules.transactions import TransactionRepository
from app.modules.users import UpdateUserDto, UserRepository


class SetUserLoyaltyExcludedUseCase(UseCase[SetUserLoyaltyExcludedDto, UserLoyaltyDto]):
    required_permission = Permission.USERS_LOYALTY_MANAGE

    def __init__(
        self,
        loyalty_repository: LoyaltyRepository,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
        recalc_dispatch: LoyaltyRecalcDispatch,
    ) -> None:
        self._loyalty_repository = loyalty_repository
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._event_publisher = event_publisher
        self._recalc_dispatch = recalc_dispatch

    async def _execute(self, actor: Actor, data: SetUserLoyaltyExcludedDto) -> UserLoyaltyDto:
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
                    "Cannot change the loyalty program of a staff account",
                    code=ErrorCode.DISCOUNT_STAFF_ACCOUNT,
                )

            updated = target
            if target.loyalty_excluded != data.excluded:
                updated = (
                    await self._user_repository.update_fields(
                        data.user_id, UpdateUserDto(loyalty_excluded=data.excluded)
                    )
                    or target
                )
                await self._event_publisher.publish(
                    UserLoyaltyExclusionChangedEvent(
                        actor=actor, target=target, excluded=data.excluded
                    )
                )
                await self._uow.after_commit(
                    partial(self._recalc_dispatch.kiq, user_ids=[data.user_id])
                )
            result = await build_user_loyalty(
                updated,
                self._loyalty_repository,
                self._transaction_repository,
                self._pricing_repository,
            )
        logger.info(
            f"{actor.log} Set loyalty exclusion of user '{data.user_id}' to {data.excluded}"
        )
        return result
