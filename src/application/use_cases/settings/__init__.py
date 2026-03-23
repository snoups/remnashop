from typing import Final

from src.application.common import Interactor

from .commands.access import ChangeAccessMode, TogglePayments, ToggleRegistration
from .commands.currency import UpdateDefaultCurrency
from .commands.notifications import ToggleNotification
from .commands.referral import (
    ToggleReferralSystem,
    UpdateReferralAccrualStrategy,
    UpdateReferralLevel,
    UpdateReferralRewardConfig,
    UpdateReferralRewardStrategy,
    UpdateReferralRewardType,
)
from .commands.backup import (
    ToggleBackupEnabled,
    ToggleBackupSendToChat,
    UpdateBackupInterval,
    UpdateBackupMaxFiles,
)
from .commands.backup import (
    ToggleBackupEnabled,
    ToggleBackupSendToChat,
    UpdateBackupInterval,
    UpdateBackupMaxFiles,
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
    ToggleRegistration,
    UpdateChannelRequirement,
    UpdateReferralAccrualStrategy,
    UpdateReferralLevel,
    UpdateReferralRewardConfig,
    UpdateReferralRewardStrategy,
    UpdateReferralRewardType,
    UpdateRulesRequirement,
    UpdateDefaultCurrency,
    ToggleBackupEnabled,
    ToggleBackupSendToChat,
    UpdateBackupInterval,
    UpdateBackupMaxFiles,
)
