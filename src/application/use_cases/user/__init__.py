from typing import Final

from src.application.common import Interactor

from .commands.blocking import SetBotBlockedStatus, ToggleUserBlockedStatus, UnblockAllUsers
from .commands.deletion import DeleteUserCompletely
from .commands.messaging import SendMessageToUser
from .commands.profile_edit import (
    ChangeUserPoints,
    SetUserPersonalDiscount,
    SetUserPurchaseDiscount,
    ToggleUserTrialAvailable,
)
from .commands.registration import GetOrCreateUser, UpdateUserFromTelegram
from .commands.roles import GetAdmins, RevokeRole, SetUserRole
from .queries.plans import GetAvailablePlanByCode, GetAvailablePlans, GetAvailableTrial
from .queries.profile import GetUserDevices, GetUserProfile, GetUserProfileSubscription
from .queries.search import SearchUsers

USER_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    GetAdmins,
    GetOrCreateUser,
    DeleteUserCompletely,
    SetBotBlockedStatus,
    ToggleUserBlockedStatus,
    RevokeRole,
    SetUserRole,
    SearchUsers,
    UnblockAllUsers,
    GetUserProfile,
    GetUserProfileSubscription,
    GetUserDevices,
    GetAvailablePlans,
    SetUserPersonalDiscount,
    SetUserPurchaseDiscount,
    ToggleUserTrialAvailable,
    ChangeUserPoints,
    SendMessageToUser,
    GetAvailableTrial,
    GetAvailablePlanByCode,
    UpdateUserFromTelegram,
)
