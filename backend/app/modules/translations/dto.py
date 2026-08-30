from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import Locale


class TranslationEntryDto(BaseDto, TimestampMixin):
    locale: Locale
    message_id: str
    attribute_id: str
    value: str
    default_value: str
