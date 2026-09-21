from pydantic import BaseModel

from app.core.enums import Locale


class BannerMetaResponse(BaseModel):
    name: str
    locale: Locale
    content_type: str
    size_bytes: int


class BannerListResponse(BaseModel):
    banners: list[BannerMetaResponse]
    available_locales: list[Locale]
