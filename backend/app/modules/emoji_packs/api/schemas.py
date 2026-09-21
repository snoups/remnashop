from pydantic import BaseModel, Field


class EmojiPackItemResponse(BaseModel):
    custom_emoji_id: str
    fallback_emoji: str


class EmojiPackResponse(BaseModel):
    set_name: str
    title: str
    items: list[EmojiPackItemResponse]


class ImportEmojiPackRequest(BaseModel):
    link: str = Field(min_length=1, max_length=256)
