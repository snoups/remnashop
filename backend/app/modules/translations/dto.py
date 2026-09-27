from dataclasses import dataclass

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import Locale


class TranslationEntryDto(BaseDto, TimestampMixin):
    locale: Locale
    message_id: str
    attribute_id: str
    value: str
    default_value: str


@dataclass(frozen=True, kw_only=True)
class TranslationTextExportDto:
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


@dataclass(frozen=True, kw_only=True)
class TranslationsExportDto:
    version: int
    texts: list[TranslationTextExportDto]


@dataclass(frozen=True, kw_only=True)
class TranslationsImportResultDto:
    applied: int
    skipped: int
