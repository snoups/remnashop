from typing import Final

from src.application.common import Interactor

from .commands.management import (
    DeleteUserAllDevices,
    DeleteUserDevice,
    ReissueSubscription,
    ReissueUserSubscription,
    ResetUserTraffic,
)
from .commands.relink import RelinkRemnaUsers
from .commands.synchronization import SyncAllUsersFromBot, SyncAllUsersFromPanel, SyncRemnaUser
from .queries.squads import GetExternalSquads, GetInternalSquads

REMNAWAVE_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    RelinkRemnaUsers,
    SyncAllUsersFromBot,
    SyncAllUsersFromPanel,
    SyncRemnaUser,
    DeleteUserDevice,
    DeleteUserAllDevices,
    ResetUserTraffic,
    ReissueSubscription,
    ReissueUserSubscription,
    GetInternalSquads,
    GetExternalSquads,
)
