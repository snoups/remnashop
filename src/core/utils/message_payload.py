from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from src.core.enums import MediaType, MessageEffect
from src.core.utils.types import AnyInputFile, AnyKeyboard


class MessagePayload(BaseModel):
    i18n_key: str
    i18n_kwargs: dict[str, Any] = {}

    media: Optional[AnyInputFile] = None
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
