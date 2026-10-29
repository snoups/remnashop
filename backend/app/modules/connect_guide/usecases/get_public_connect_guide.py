from app.core.db.uow import UnitOfWork
from app.modules.connect_guide.catalog import ConnectCatalog
from app.modules.connect_guide.repository import ConnectGuideRepository


class GetPublicConnectGuideUseCase:
    """Zero-session: the cabinet's connect screen, and the browser page a Mini App deep link hops
    through, which has no cabinet session. A switched-off guide is an empty catalog."""

    def __init__(self, connect_guide_repository: ConnectGuideRepository, uow: UnitOfWork) -> None:
        self._connect_guide_repository = connect_guide_repository
        self._uow = uow

    async def execute(self) -> ConnectCatalog:
        async with self._uow:
            guide = await self._connect_guide_repository.get()
        return guide.catalog if guide.enabled else ConnectCatalog()
