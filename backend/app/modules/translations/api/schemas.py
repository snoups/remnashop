from pydantic import BaseModel

from app.core.enums import Locale


class TranslationEntryItem(BaseModel):
    locale: Locale
    message_id: str
    attribute_id: str
    value: str
    default_value: str


class UpdateTranslationRequest(BaseModel):
    value: str


class TranslationTextExportItem(BaseModel):
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


class TranslationsExportPayload(BaseModel):
    version: int
    texts: list[TranslationTextExportItem]


class TranslationsImportResult(BaseModel):
    applied: int
    skipped: int
