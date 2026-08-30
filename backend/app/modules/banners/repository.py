from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.banner import Banner
from app.core.enums import BannerName, Locale
from app.modules.banners.dto import BannerDto, UploadBannerDto


class BannerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: Banner) -> BannerDto:
        return BannerDto(
            id=row.id,
            name=row.name,
            locale=row.locale,
            content_type=row.content_type,
            extension=row.extension,
            size_bytes=row.size_bytes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get(self, name: BannerName, locale: Locale) -> Optional[BannerDto]:
        row = await self.session.scalar(
            select(Banner).where(Banner.name == name, Banner.locale == locale)
        )
        return self._to_dto(row) if row is not None else None

    async def list_all(self) -> list[BannerDto]:
        result = await self.session.execute(select(Banner).order_by(Banner.name, Banner.locale))
        return [self._to_dto(row) for row in result.scalars()]

    async def upsert(self, data: UploadBannerDto) -> BannerDto:
        row = await self.session.scalar(
            select(Banner).where(Banner.name == data.name, Banner.locale == data.locale)
        )
        if row is None:
            row = Banner(name=data.name, locale=data.locale)
            self.session.add(row)

        row.content_type = data.content_type
        row.extension = data.extension
        row.size_bytes = data.size_bytes

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def delete(self, name: BannerName, locale: Locale) -> None:
        row = await self.session.scalar(
            select(Banner).where(Banner.name == name, Banner.locale == locale)
        )
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()

    async def find_for_display(
        self, name: BannerName, locale: Locale, default_locale: Locale
    ) -> Optional[BannerDto]:
        candidates = [(name, locale), (BannerName.DEFAULT, locale)]
        if locale != default_locale:
            candidates += [(name, default_locale), (BannerName.DEFAULT, default_locale)]

        for candidate_name, candidate_locale in candidates:
            banner = await self.get(candidate_name, candidate_locale)
            if banner is not None:
                return banner
        return None
