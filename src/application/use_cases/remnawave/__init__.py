from typing import Final

from src.application.common import Interactor

from .commands.management import (
    DeleteUserAllDevices,
    DeleteUserDevice,
    ReissueSubscription,
    ReissueUserSubscription,
    ResetUserTraffic,
)
from .commands.synchronization import SyncAllUsersFromBot, SyncAllUsersFromPanel, SyncRemnaUser

REMNAWAVE_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    SyncAllUsersFromBot,
    SyncAllUsersFromPanel,
    SyncRemnaUser,
    DeleteUserDevice,
    DeleteUserAllDevices,
    ResetUserTraffic,
    ReissueSubscription,
    ReissueUserSubscription,
)
