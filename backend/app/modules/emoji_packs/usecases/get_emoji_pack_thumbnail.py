from typing import Final

from app.core.db.uow import UnitOfWork
from app.core.exceptions import NotFoundError
from app.modules.emoji_packs.repository import EmojiPackRepository

_WEBP_MAGIC: Final[bytes] = b"RIFF"


class GetEmojiPackThumbnailUseCase:
    def __init__(self, emoji_pack_repository: EmojiPackRepository, uow: UnitOfWork) -> None:
        self._emoji_pack_repository = emoji_pack_repository
        self._uow = uow

    async def execute(self, custom_emoji_id: str) -> tuple[bytes, str]:
        async with self._uow:
            data = await self._emoji_pack_repository.get_thumbnail(custom_emoji_id)
        if not data:
            raise NotFoundError(f"No thumbnail for emoji {custom_emoji_id}")
        return data, "image/webp" if data.startswith(_WEBP_MAGIC) else "image/jpeg"
