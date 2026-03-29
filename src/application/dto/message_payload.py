from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from src.core.enums import MediaType, MessageEffectId
from src.core.types import AnyKeyboard


@dataclass(frozen=True)
class MediaDescriptorDto:
    kind: Literal["file_id", "fs", "bytes"]
    value: str
    filename: Optional[str] = None


@dataclass(kw_only=True)
class MessagePayloadDto:
    i18n_key: str
    i18n_kwargs: dict[str, Any] = field(default_factory=dict)

    media: Optional[MediaDescriptorDto] = None
    media_type: Optional[MediaType] = None

    reply_markup: Optional[AnyKeyboard] = None
    disable_default_markup: bool = True

    delete_after: Optional[int] = 5
    thread_id: Optional[int] = None
    message_effect: Optional[MessageEffectId] = None
    disable_notification: bool = False

    @property
    def is_text(self) -> bool:
        return not self.media_type

    @property
    def is_photo(self) -> bool:
        return self.media_type is MediaType.PHOTO

    @property
    def is_video(self) -> bool:
        return self.media_type is MediaType.VIDEO

    @property
    def is_document(self) -> bool:
        return self.media_type is MediaType.DOCUMENT
