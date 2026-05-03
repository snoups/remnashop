from typing import Final

from src.application.common import Interactor

from .commands.access import ChangeAccessMode, TogglePayments, ToggleRegistration
from .commands.currency import UpdateDefaultCurrency
from .commands.notifications import ToggleNotification
from .commands.referral import (
    ToggleReferralSystem,
    ToggleReferralTrialReward,
    UpdateReferralAccrualStrategy,
    UpdateReferralLevel,
    UpdateReferralRewardConfig,
    UpdateReferralRewardStrategy,
    UpdateReferralRewardType,
)
from .commands.requirements import (
    ToggleConditionRequirement,
    UpdateChannelRequirement,
    UpdateRulesRequirement,
)

SETTINGS_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    ChangeAccessMode,
    ToggleConditionRequirement,
    ToggleNotification,
    TogglePayments,
    ToggleReferralSystem,
    ToggleReferralTrialReward,
    ToggleRegistration,
    UpdateChannelRequirement,
    UpdateReferralAccrualStrategy,
    UpdateReferralLevel,
    UpdateReferralRewardConfig,
    UpdateReferralRewardStrategy,
    UpdateReferralRewardType,
    UpdateRulesRequirement,
    UpdateDefaultCurrency,
)
