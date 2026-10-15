from dataclasses import dataclass
from typing import Final

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import Locale


class TranslationEntryDto(BaseDto, TimestampMixin):
    locale: Locale
    message_id: str
    attribute_id: str
    value: str
    default_value: str


@dataclass(frozen=True, kw_only=True)
class ActiveLocalesDto:
    active: list[Locale]
    default: Locale

    @property
    def available(self) -> list[Locale]:
        return [locale for locale in Locale if locale not in self.active]


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


@dataclass(frozen=True, kw_only=True)
class TranslationsImportDto:
    version: int
    texts: list[TranslationTextExportDto]


@dataclass(frozen=True, kw_only=True)
class ResetTranslationDto:
    locale: Locale
    message_id: str
    attribute_id: str


@dataclass(frozen=True, kw_only=True)
class UpdateTranslationDto:
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


EXPORT_VERSION: Final[int] = 1
