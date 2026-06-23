from typing import Final

from src.application.common import Interactor

from .commands import (
    AddManualGiveawayEntry,
    ArchiveGiveawayCampaign,
    CreateGiveawayCampaign,
    DeleteGiveawayCampaign,
    RegisterGiveawayEntry,
    SaveGiveawayPhone,
    SelectGiveawayWinner,
    SetGiveawayStatus,
    UpdateGiveawayRules,
)
from .queries import (
    GetClientGiveawayConditions,
    GetClientGiveawayDetails,
    ListClientGiveaways,
)

GIVEAWAY_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    AddManualGiveawayEntry,
    CreateGiveawayCampaign,
    SetGiveawayStatus,
    ArchiveGiveawayCampaign,
    DeleteGiveawayCampaign,
    RegisterGiveawayEntry,
    SaveGiveawayPhone,
    SelectGiveawayWinner,
    UpdateGiveawayRules,
    ListClientGiveaways,
    GetClientGiveawayDetails,
    GetClientGiveawayConditions,
)
