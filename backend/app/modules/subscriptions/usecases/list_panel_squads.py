import asyncio

from remnapy import RemnawaveSDK

from app.core.actor import Actor
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import PanelSquadDto


class ListPanelSquadsUseCase(UseCase[None, list[PanelSquadDto]]):
    """Internal and external squads together: a subscription stores only their
    uuids, the names live in the panel."""

    required_permission = Permission.SUBSCRIPTIONS_PANEL_SQUADS_VIEW

    def __init__(self, remnawave_sdk: RemnawaveSDK) -> None:
        self._remnawave_sdk = remnawave_sdk

    async def _execute(self, actor: Actor, data: None) -> list[PanelSquadDto]:
        internal, external = await asyncio.gather(
            self._remnawave_sdk.internal_squads.get_internal_squads(),
            self._remnawave_sdk.external_squads.get_external_squads(),
        )
        return [
            *(
                PanelSquadDto(uuid=squad.uuid, name=squad.name, kind="internal")
                for squad in internal.internal_squads
            ),
            *(
                PanelSquadDto(uuid=squad.uuid, name=squad.name, kind="external")
                for squad in external.external_squads
            ),
        ]
