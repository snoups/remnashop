from typing import Final, Optional

from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.modules.emoji_packs.repository import EmojiPackRepository
from app.modules.emoji_packs.telegram_api import LOTTIE_KIND

# A .tgs is gzipped lottie JSON: handing it over with the encoding it already
# has lets the browser inflate it, so nothing here ever decompresses.
_MEDIA_TYPES: Final[dict[str, tuple[str, Optional[str]]]] = {
    LOTTIE_KIND: ("application/json", "gzip"),
}
_VIDEO_MEDIA_TYPE: Final[tuple[str, Optional[str]]] = ("video/webm", None)


class GetEmojiPackAnimationUseCase:
    def __init__(self, emoji_pack_repository: EmojiPackRepository, uow: UnitOfWork) -> None:
        self._emoji_pack_repository = emoji_pack_repository
        self._uow = uow

    async def execute(self, custom_emoji_id: str) -> tuple[bytes, str, Optional[str]]:
        async with self._uow:
            found = await self._emoji_pack_repository.find_animation(custom_emoji_id)
        if found is None:
            raise NotFoundError(
                f"No animation for emoji {custom_emoji_id}", code=ErrorCode.EMOJI_MEDIA_NOT_FOUND
            )

        data, kind = found
        media_type, encoding = _MEDIA_TYPES.get(kind, _VIDEO_MEDIA_TYPE)
        return data, media_type, encoding
