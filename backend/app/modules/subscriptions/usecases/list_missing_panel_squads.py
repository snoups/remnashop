from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import MissingSquadDto
from app.modules.subscriptions.panel_squads import PanelSquadCatalog, missing_by_kind
from app.modules.subscriptions.repository import SubscriptionRepository


class ListMissingPanelSquadsUseCase(UseCase[None, list[MissingSquadDto]]):
    """Squads the subscriptions a sync to the panel covers still hold but the
    panel no longer has: the admin picks their replacements before it starts."""

    required_permission = Permission.SUBSCRIPTIONS_PANEL_MISSING_SQUADS_VIEW

    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        squad_catalog: PanelSquadCatalog,
        uow: UnitOfWork,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._squad_catalog = squad_catalog
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> list[MissingSquadDto]:
        async with self._uow:
            subscriptions = await self._subscription_repository.list_non_terminal()
        known = frozenset(squad.uuid for squad in await self._squad_catalog.fetch())
        return missing_by_kind(
            ((s.internal_squads, s.external_squad) for s in subscriptions), known
        )
