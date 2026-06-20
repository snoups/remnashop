from typing import Final

from src.application.common import Interactor

from .commands import (
    ArchiveGiveawayCampaign,
    CreateGiveawayCampaign,
    DeleteGiveawayCampaign,
    RegisterGiveawayEntry,
    SaveGiveawayPhone,
    SelectGiveawayWinner,
    SetGiveawayStatus,
)

GIVEAWAY_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    CreateGiveawayCampaign,
    SetGiveawayStatus,
    ArchiveGiveawayCampaign,
    DeleteGiveawayCampaign,
    RegisterGiveawayEntry,
    SaveGiveawayPhone,
    SelectGiveawayWinner,
)
