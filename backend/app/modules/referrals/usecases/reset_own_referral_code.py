from datetime import timedelta

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.events import ReferralCodeResetEvent
from app.modules.settings import SettingsRepository
from app.modules.users import UserDto, UserRepository


class ResetOwnReferralCodeUseCase(UseCase[None, UserDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        user_repository: UserRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: UserDto, data: None) -> UserDto:
        async with self._uow:
            shop_settings = await self._settings_repository.get_shop_settings()
            if not shop_settings.referral_reset_enabled:
                raise ValidationError(
                    "Referral code reset is disabled", code=ErrorCode.REFERRAL_RESET_DISABLED
                )
            updated = await self._user_repository.reset_own_referral_code(
                actor.id, timedelta(hours=shop_settings.referral_reset_cooldown_hours)
            )
            await self._event_publisher.publish(ReferralCodeResetEvent(actor=actor, target=updated))

        logger.info(f"{actor.log} Reset own referral code")
        return updated
