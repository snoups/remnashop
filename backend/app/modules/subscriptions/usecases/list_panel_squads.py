from app.core.actor import Actor
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import PanelSquadDto
from app.modules.subscriptions.panel_squads import PanelSquadCatalog


class ListPanelSquadsUseCase(UseCase[None, list[PanelSquadDto]]):
    """Internal and external squads together: a subscription stores only their
    uuids, the names live in the panel."""

    required_permission = Permission.SUBSCRIPTIONS_PANEL_SQUADS_VIEW

    def __init__(self, squad_catalog: PanelSquadCatalog) -> None:
        self._squad_catalog = squad_catalog

    async def _execute(self, actor: Actor, data: None) -> list[PanelSquadDto]:
        return await self._squad_catalog.fetch()
