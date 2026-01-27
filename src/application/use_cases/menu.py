from dataclasses import dataclass
from typing import Optional

from src.application.common import Interactor
from src.application.common.dao import PlanDao, SettingsDao, SubscriptionDao
from src.application.common.policy import Permission
from src.application.dto import PlanDto, SubscriptionDto, UserDto
from src.application.services import BotService


@dataclass(frozen=True)
class GetMenuDataResultDto:
    is_referral_enabled: bool
    is_trial_available: bool
    available_trial: Optional[PlanDto]
    current_subscription: Optional[SubscriptionDto]
    referral_url: str


class GetMenuData(Interactor[None, GetMenuDataResultDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        plan_dao: PlanDao,
        settings_dao: SettingsDao,
        subscription_dao: SubscriptionDao,
        bot_service: BotService,
    ) -> None:
        self.plan_dao = plan_dao
        self.settings_dao = settings_dao
        self.subscription_dao = subscription_dao
        self.bot_service = bot_service

    async def _execute(self, actor: UserDto, data: None) -> GetMenuDataResultDto:
        current_subscription = await self.subscription_dao.get_current(actor.telegram_id)

        plan = None
        if actor.is_trial_available:
            plan = await self.plan_dao.get_trial_available_for_user(actor.telegram_id)

        settings = await self.settings_dao.get()
        is_referral_enabled = settings.referral.enable

        referral_url = await self.bot_service.get_referral_url(actor.referral_code)

        return GetMenuDataResultDto(
            is_referral_enabled=is_referral_enabled,
            is_trial_available=actor.is_trial_available,
            available_trial=plan,
            current_subscription=current_subscription,
            referral_url=referral_url,
        )
