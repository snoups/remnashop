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


@dataclass(frozen=True, kw_only=True)
class BannerImageQueryDto:
    name: str
    locale: Locale
    # the file the bot would send for this window and language: the shared banner,
    # then the default language, when this exact one is missing
    fallback: bool = False


@dataclass(frozen=True, kw_only=True)
class BannerImageDto:
    data: bytes
    content_type: str
    # the banner actually served, which a fallback may have changed
    name: str
    locale: Locale
