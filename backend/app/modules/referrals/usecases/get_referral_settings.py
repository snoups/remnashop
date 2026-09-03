from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.referrals.dto import ReferralSettingsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.users import UserDto


class GetReferralSettingsUseCase(UseCase[None, ReferralSettingsDto]):
    required_permission = Permission.REFERRALS_SETTINGS_VIEW

    def __init__(self, referral_repository: ReferralRepository) -> None:
        self._referral_repository = referral_repository

    async def _execute(self, actor: UserDto, data: None) -> ReferralSettingsDto:
        return await self._referral_repository.get_settings()
