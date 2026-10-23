from pydantic import BaseModel

from app.core.enums import Locale


class TranslationEntryResponse(BaseModel):
    locale: Locale
    message_id: str
    attribute_id: str
    value: str
    default_value: str


class UpdateTranslationRequest(BaseModel):
    value: str


class TranslationTextExportResponse(BaseModel):
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


class TranslationTextImportRequest(BaseModel):
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


class TranslationsExportResponse(BaseModel):
    version: int
    texts: list[TranslationTextExportResponse]


class TranslationsImportRequest(BaseModel):
    version: int
    texts: list[TranslationTextImportRequest]


class TranslationsImportResponse(BaseModel):
    applied: int
    skipped: int


class TranslationEntryListResponse(BaseModel):
    items: list[TranslationEntryResponse]
    total: int


class ActiveLocalesResponse(BaseModel):
    active: list[Locale]
    available: list[Locale]
    default: Locale


class UpdateLocalesRequest(BaseModel):
    default: Locale
