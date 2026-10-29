from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.connect_guide_settings import ConnectGuideSettings
from app.core.db.singleton import SINGLETON_ID, get_or_create_singleton
from app.modules.connect_guide.catalog import ConnectCatalog
from app.modules.connect_guide.defaults import DEFAULT_CATALOG
from app.modules.connect_guide.dto import ConnectGuideDto


class ConnectGuideRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: Optional[ConnectGuideSettings]) -> ConnectGuideDto:
        if row is None or row.catalog is None:
            return ConnectGuideDto(
                enabled=row.enabled if row is not None else True,
                catalog=DEFAULT_CATALOG,
                is_default=True,
            )
        return ConnectGuideDto(
            enabled=row.enabled,
            catalog=ConnectCatalog.model_validate(row.catalog),
            is_default=False,
        )

    async def get(self) -> ConnectGuideDto:
        return self._to_dto(await self.session.get(ConnectGuideSettings, SINGLETON_ID))

    async def save(self, enabled: bool, catalog: ConnectCatalog) -> ConnectGuideDto:
        row = await get_or_create_singleton(self.session, ConnectGuideSettings, SINGLETON_ID)
        row.enabled = enabled
        row.catalog = catalog.model_dump(mode="json")
        await self.session.flush()
        return self._to_dto(row)

    async def reset(self) -> ConnectGuideDto:
        row = await self.session.get(ConnectGuideSettings, SINGLETON_ID)
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()
        return self._to_dto(None)
