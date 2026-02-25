from dataclasses import dataclass, field
from typing import Final, Optional

from src.application.common import Interactor, TranslatorRunner
from src.application.common.dao import PlanDao, SettingsDao, SubscriptionDao
from src.application.common.policy import Permission
from src.application.dto import MenuButtonDto, PlanDto, SubscriptionDto, UserDto
from src.application.services import BotService
from src.application.use_cases.user import GetAvailableTrial


@dataclass(frozen=True)
class GetMenuDataResultDto:
    is_referral_enabled: bool
    is_trial_available: bool
    available_trial: Optional[PlanDto]
    current_subscription: Optional[SubscriptionDto]
    referral_url: str
    custom_buttons: list[MenuButtonDto] = field(default_factory=list)


class GetMenuData(Interactor[None, GetMenuDataResultDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        plan_dao: PlanDao,
        settings_dao: SettingsDao,
        subscription_dao: SubscriptionDao,
        bot_service: BotService,
        i18n: TranslatorRunner,
        get_available_trial: GetAvailableTrial,
    ) -> None:
        self.plan_dao = plan_dao
        self.settings_dao = settings_dao
        self.subscription_dao = subscription_dao
        self.bot_service = bot_service
        self.i18n = i18n
        self.get_available_trial = get_available_trial

    async def _execute(self, actor: UserDto, data: None) -> GetMenuDataResultDto:
        current_subscription = await self.subscription_dao.get_current(actor.telegram_id)

        plan = None
        if actor.is_trial_available:
            plan = await self.get_available_trial.system(actor)

        settings = await self.settings_dao.get()
        is_referral_enabled = settings.referral.enable
        referral_url = await self.bot_service.get_referral_url(actor.referral_code)

        custom_buttons = []
        for button in settings.menu.buttons:
            if button.is_active and actor.role.value >= button.required_role.value:
                translated_text = self.i18n.get(button.text)
                button.text = translated_text
                custom_buttons.append(button)

        return GetMenuDataResultDto(
            is_referral_enabled=is_referral_enabled,
            is_trial_available=actor.is_trial_available,
            available_trial=plan,
            current_subscription=current_subscription,
            referral_url=referral_url,
            custom_buttons=custom_buttons,
        )


MENU_USE_CASES: Final[tuple[type[Interactor], ...]] = (GetMenuData,)
