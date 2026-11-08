from typing import Optional
from uuid import UUID

from app.modules.subscriptions.dto import PanelSquadDto
from app.modules.subscriptions.panel_squads import PanelSquadCatalog


class FixedPanelSquads(PanelSquadCatalog):
    """The panel's squads without a panel; None skips the cached check, as an outage does."""

    def __init__(self, known: Optional[frozenset[UUID]] = None) -> None:
        self._known = known

    async def fetch(self) -> list[PanelSquadDto]:
        return [
            PanelSquadDto(uuid=squad, name=str(squad), kind="internal")
            for squad in self._known or ()
        ]

    async def known(self) -> Optional[frozenset[UUID]]:
        return self._known
