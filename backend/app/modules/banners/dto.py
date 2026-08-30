from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import BannerName, Locale


class BannerDto(BaseDto, TimestampMixin):
    name: BannerName
    locale: Locale
    content_type: str
    extension: str
    size_bytes: int


class BannerListDto(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore")

    banners: list[BannerDto]
    available_locales: list[Locale]


@dataclass(frozen=True, kw_only=True)
class UploadBannerDto:
    name: BannerName
    locale: Locale
    content_type: str
    extension: str
    size_bytes: int


@dataclass(frozen=True, kw_only=True)
class BannerKeyDto:
    name: BannerName
    locale: Locale
