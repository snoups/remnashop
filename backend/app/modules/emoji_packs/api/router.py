from typing import Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Response

from app.api.errors import error_responses
from app.modules.emoji_packs.usecases import (
    GetEmojiPackAnimationUseCase,
    GetEmojiPackThumbnailUseCase,
)

# Sessionless on purpose: an <img> carries no bearer token, and the bytes are
# public Telegram artwork keyed by an id that is itself public.
router = APIRouter(prefix="/emoji-packs", tags=["emoji-packs"])

_CACHE_CONTROL: Final[str] = "public, max-age=31536000, immutable"


@router.get("/thumbnails/{custom_emoji_id}", responses=error_responses(404))
@inject
async def get_emoji_thumbnail(
    custom_emoji_id: str,
    use_case: FromDishka[GetEmojiPackThumbnailUseCase],
) -> Response:
    data, content_type = await use_case.execute(custom_emoji_id)
    return Response(
        content=data, media_type=content_type, headers={"Cache-Control": _CACHE_CONTROL}
    )


@router.get("/animations/{custom_emoji_id}", responses=error_responses(404))
@inject
async def get_emoji_animation(
    custom_emoji_id: str,
    use_case: FromDishka[GetEmojiPackAnimationUseCase],
) -> Response:
    data, content_type, encoding = await use_case.execute(custom_emoji_id)

    headers = {"Cache-Control": _CACHE_CONTROL}
    if encoding is not None:
        headers["Content-Encoding"] = encoding
    return Response(content=data, media_type=content_type, headers=headers)
