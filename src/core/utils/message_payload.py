from typing import Any, Optional, Self

from pydantic import BaseModel, ConfigDict

from src.core.enums import MediaType, MessageEffect
from src.core.utils.types import AnyInputFile, AnyKeyboard


class MessagePayload(BaseModel):
    i18n_key: str
    i18n_kwargs: dict[str, Any] = {}

    media: Optional[AnyInputFile] = None
    media_id: Optional[str] = None
    media_type: Optional[MediaType] = None
    reply_markup: Optional[AnyKeyboard] = None
    auto_delete_after: Optional[int] = 5
    add_close_button: bool = False
    message_effect: Optional[MessageEffect] = None

    model_config = ConfigDict(
        extra="ignore",
        from_attributes=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    @classmethod
    def not_deleted(
        cls,
        i18n_key: str,
        i18n_kwargs: dict[str, Any] = {},
        media: Optional[AnyInputFile] = None,
        media_id: Optional[str] = None,
        media_type: Optional[MediaType] = None,
        reply_markup: Optional[AnyKeyboard] = None,
        auto_delete_after: Optional[int] = None,
        add_close_button: bool = True,
        message_effect: Optional[MessageEffect] = None,
    ) -> Self:
        data = {
            "i18n_key": i18n_key,
            "i18n_kwargs": i18n_kwargs,
            "media": media,
            "media_id": media_id,
            "media_type": media_type,
            "reply_markup": reply_markup,
            "auto_delete_after": auto_delete_after,
            "add_close_button": add_close_button,
            "message_effect": message_effect,
        }
        return cls(**data)
