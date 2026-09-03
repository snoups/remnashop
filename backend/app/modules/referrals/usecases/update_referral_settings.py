from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import ReferralSettingsDto, UpdateReferralSettingsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto


class UpdateReferralSettingsUseCase(UseCase[UpdateReferralSettingsDto, ReferralSettingsDto]):
    required_permission = Permission.REFERRALS_SETTINGS_MANAGE

    def __init__(self, referral_repository: ReferralRepository, uow: UnitOfWork) -> None:
        self._referral_repository = referral_repository
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: UpdateReferralSettingsDto
    ) -> ReferralSettingsDto:
        async with self._uow:
            updated = await self._referral_repository.update_settings(data)
            await self._uow.commit()
        logger.info(f"{actor.log} Updated referral settings")
        return updated
