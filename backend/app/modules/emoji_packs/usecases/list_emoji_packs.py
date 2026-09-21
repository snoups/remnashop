from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.emoji_packs.dto import EmojiPackDto
from app.modules.emoji_packs.repository import EmojiPackRepository
from app.modules.users import UserDto


class ListEmojiPacksUseCase(UseCase[None, list[EmojiPackDto]]):
    required_permission = Permission.EMOJI_PACKS_VIEW

    def __init__(self, emoji_pack_repository: EmojiPackRepository, uow: UnitOfWork) -> None:
        self._emoji_pack_repository = emoji_pack_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> list[EmojiPackDto]:
        async with self._uow:
            return await self._emoji_pack_repository.list_all()
