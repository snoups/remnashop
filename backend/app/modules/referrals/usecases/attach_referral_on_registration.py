from decimal import Decimal

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import ReferralLevel, ReferralRewardType
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.referrals.dto import AttachReferralOnRegistrationDto, ReferralSettingsDto
from app.modules.referrals.events import InviteeRewardIssuedEvent, ReferralAttachedEvent
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto, UserRepository


class AttachReferralOnRegistrationUseCase(UseCase[AttachReferralOnRegistrationDto, None]):
    required_permission = None

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

    async def _execute(self, actor: Actor, data: AttachReferralOnRegistrationDto) -> None:
        # a stale, foreign or disabled link just leaves the newcomer unattached
        async with self._uow:
            settings = await self._referral_repository.get_settings()
            user = await self._user_repository.find_by_id(data.user_id)
            referrer = await self._user_repository.find_by_referral_code(data.referral_code)
        if user is None or user.deleted_at is not None or not settings.enabled:
            return
        if referrer is None or referrer.id == user.id or referrer.is_blocked:
            logger.info(f"{user.log} Referral code '{data.referral_code}' not usable, skipping")
            return
        if await self._is_in_own_downline(referrer.id, user.id, settings.max_level):
            logger.info(f"{user.log} Referral code '{data.referral_code}' would close a cycle")
            return
        level = await self._compute_level(referrer.id, settings.max_level)

        try:
            async with self._uow:
                await self._referral_repository.create_referral(
                    referrer_id=referrer.id, referred_id=user.id, level=level
                )
                await self._event_publisher.publish(
                    ReferralAttachedEvent(user=user, referrer_id=referrer.id)
                )
                await self._reward_invitee(user, settings)
        except ConflictError:
            # a redelivered task: the edge, and its reward, already exist
            logger.info(f"{user.log} Already attached to a referrer, skipping")
            return
        logger.info(f"{user.log} Attached to referrer '{referrer.id}' at level '{level}'")

    async def _reward_invitee(self, user: UserDto, settings: ReferralSettingsDto) -> None:
        amount = settings.invitee_reward_amount
        if amount <= 0:
            return
        if settings.invitee_reward_type is ReferralRewardType.EXTRA_DAYS:
            await self._user_repository.credit_bonus_days(user.id, amount)
        else:
            await self._user_repository.credit_points(user.id, Decimal(amount))
        await self._event_publisher.publish(
            InviteeRewardIssuedEvent(
                user=user, reward_type=settings.invitee_reward_type, amount=amount
            )
        )

    async def _is_in_own_downline(self, referrer_id: int, user_id: int, max_level: int) -> bool:
        # walking up from the referrer: meeting the user means a cycle, and the
        # pair would earn off each other forever; a longer chain can't reward across it
        async with self._uow:
            current_id = referrer_id
            for _ in range(max_level):
                if current_id == user_id:
                    return True
                edge = await self._referral_repository.find_by_referred_id(current_id)
                if edge is None or edge.referrer_id is None:
                    return False
                current_id = edge.referrer_id
            return current_id == user_id

    async def _compute_level(self, referrer_id: int, max_level: int) -> int:
        async with self._uow:
            parent_edge = await self._referral_repository.find_by_referred_id(referrer_id)
            if parent_edge is None:
                return ReferralLevel.FIRST
            return min(parent_edge.level + 1, max_level)
