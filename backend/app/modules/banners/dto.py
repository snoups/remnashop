from dataclasses import dataclass

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import Locale


class BannerDto(BaseDto, TimestampMixin):
    name: str
    locale: Locale
    content_type: str
    extension: str
    size_bytes: int


@dataclass(frozen=True, kw_only=True)
class UploadBannerDto:
    name: str
    locale: Locale
    content_type: str
    extension: str
    size_bytes: int


@dataclass(frozen=True, kw_only=True)
class BannerKeyDto:
    name: str
    locale: Locale


@dataclass(frozen=True, kw_only=True)
class UploadBannerFileDto:
    name: str
    locale: Locale
    content_type: str
    data: bytes
