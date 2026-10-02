from loguru import logger

from app.core.actor import Actor
from app.core.exceptions import ValidationError
from app.core.usecase import UseCase
from app.modules.referrals.dto import AttachReferralDto, AttachReferralOnRegistrationDto
from app.modules.referrals.usecases.attach_referral import AttachReferralUseCase
from app.modules.users import UserRepository


class AttachReferralOnRegistrationUseCase(UseCase[AttachReferralOnRegistrationDto, None]):
    required_permission = None

    def __init__(
        self, user_repository: UserRepository, attach_referral_use_case: AttachReferralUseCase
    ) -> None:
        self._user_repository = user_repository
        self._attach_referral_use_case = attach_referral_use_case

    async def _execute(self, actor: Actor, data: AttachReferralOnRegistrationDto) -> None:
        user = await self._user_repository.get_by_id(data.user_id)
        if user is None:
            return
        try:
            await self._attach_referral_use_case(user, AttachReferralDto(code=data.referral_code))
        except ValidationError as error:
            # a stale or foreign link isn't a failure worth retrying
            logger.info(
                f"Referral code '{data.referral_code}' not attached to user "
                f"'{data.user_id}': {error}"
            )
