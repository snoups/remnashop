from typing import Optional

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import AccessDenial, AccessMode
from app.core.usecase import UseCase
from app.modules.access.dto import CheckRegistrationAccessDto
from app.modules.advertising import AdLinkRepository
from app.modules.settings import GetAccessSettingsUseCase
from app.modules.users import UserRepository


class CheckRegistrationAccessUseCase(UseCase[CheckRegistrationAccessDto, Optional[AccessDenial]]):
    # runs before the user exists; callable only via `.system`
    required_permission = None

    def __init__(
        self,
        get_access_settings: GetAccessSettingsUseCase,
        user_repository: UserRepository,
        ad_link_repository: AdLinkRepository,
        uow: UnitOfWork,
    ) -> None:
        self._get_access_settings = get_access_settings
        self._user_repository = user_repository
        self._ad_link_repository = ad_link_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: CheckRegistrationAccessDto
    ) -> Optional[AccessDenial]:
        settings = await self._get_access_settings.system()
        if settings.mode is AccessMode.PUBLIC and settings.registration_enabled:
            return None

        async with self._uow:
            if data.telegram_id is not None:
                existing = await self._user_repository.get_by_telegram_id(data.telegram_id)
                if existing is not None:
                    return None
            if data.email is not None:
                if await self._user_repository.get_by_email(data.email) is not None:
                    return None

            if settings.mode is AccessMode.RESTRICTED:
                denial: Optional[AccessDenial] = AccessDenial.RESTRICTED
            elif not settings.registration_enabled:
                denial = AccessDenial.REGISTRATION_DISABLED
            elif not await self._is_invited(data):
                denial = AccessDenial.INVITE_ONLY
            else:
                denial = None

        if denial is not None:
            logger.info(f"Registration refused ({denial}) for telegram_id={data.telegram_id}")
        return denial

    async def _is_invited(self, data: CheckRegistrationAccessDto) -> bool:
        if data.referral_code:
            referrer = await self._user_repository.get_by_referral_code(data.referral_code)
            if referrer is not None and not referrer.is_blocked and referrer.deleted_at is None:
                return True
        if data.ad_link_code:
            ad_link = await self._ad_link_repository.get_by_code(data.ad_link_code)
            if ad_link is not None and ad_link.is_active and ad_link.allows(data.channel):
                return True
        return False
