from dataclasses import dataclass

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import ReferralLevel
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.events import ReferralAttachedEvent
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto, UserRepository


@dataclass(frozen=True, kw_only=True)
class AttachReferralDto:
    code: str


class AttachReferralUseCase(UseCase[AttachReferralDto, UserDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        referral_repository: ReferralRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._referral_repository = referral_repository
        self._user_repository = user_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: AttachReferralDto) -> UserDto:
        async with self._uow:
            settings = await self._referral_repository.get_settings()
            if not settings.enabled:
                raise ValidationError(
                    "Referral system is disabled", code=ErrorCode.REFERRALS_DISABLED
                )

            referrer = await self._user_repository.get_by_referral_code(data.code)
            if referrer is None:
                raise ValidationError(
                    f"Referral code '{data.code}' not found", code=ErrorCode.REFERRAL_CODE_NOT_FOUND
                )
            if referrer.id == actor.id:
                raise ValidationError(
                    "Cannot use your own referral code", code=ErrorCode.REFERRAL_CODE_OWN
                )

            if await self._referral_repository.has_referrer(actor.id):
                raise ValidationError(
                    f"User '{actor.id}' already has a referrer", code=ErrorCode.REFERRER_ALREADY_SET
                )

        if await self._is_in_own_downline(
            referrer.id, actor_id=actor.id, max_level=settings.max_level
        ):
            raise ValidationError(
                "Cannot use the referral code of your own referral",
                code=ErrorCode.REFERRAL_CODE_CYCLE,
            )

        level = await self._compute_level(referrer.id, max_level=settings.max_level)

        async with self._uow:
            await self._referral_repository.create_referral(
                referrer_id=referrer.id, referred_id=actor.id, level=level
            )
            await self._event_publisher.publish(
                ReferralAttachedEvent(user=actor, referrer_id=referrer.id)
            )

        logger.info(f"{actor.log} Attached to referrer '{referrer.id}' at level '{level}'")
        return referrer

    async def _is_in_own_downline(self, referrer_id: int, *, actor_id: int, max_level: int) -> bool:
        # Walking up from the referrer: meeting the actor means attaching would
        # close a cycle, and the pair would then earn off each other forever.
        # Bounded by max_level -- a longer chain can't reward across the loop.
        async with self._uow:
            current_id = referrer_id
            for _ in range(max_level):
                if current_id == actor_id:
                    return True
                edge = await self._referral_repository.get_by_referred_id(current_id)
                if edge is None or edge.referrer_id is None:
                    return False
                current_id = edge.referrer_id
            return current_id == actor_id

    async def _compute_level(self, referrer_id: int, *, max_level: int) -> int:
        async with self._uow:
            parent_edge = await self._referral_repository.get_by_referred_id(referrer_id)
            if parent_edge is None:
                return ReferralLevel.FIRST
            return min(parent_edge.level + 1, max_level)
