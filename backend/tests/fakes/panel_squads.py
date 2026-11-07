from typing import Optional
from uuid import UUID

from app.modules.subscriptions.panel_squads import PanelSquadCatalog


class FixedPanelSquads(PanelSquadCatalog):
    """The panel's squads without a panel; None skips the check, as an outage does."""

    def __init__(self, known: Optional[frozenset[UUID]] = None) -> None:
        self._known = known

    async def known(self) -> Optional[frozenset[UUID]]:
        return self._known
