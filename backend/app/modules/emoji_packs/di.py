from dishka import Provider, Scope, provide

from app.modules.emoji_packs.repository import EmojiPackRepository
from app.modules.emoji_packs.usecases import (
    DeleteEmojiPackUseCase,
    ImportEmojiPackUseCase,
    ListEmojiPacksUseCase,
)


class EmojiPacksProvider(Provider):
    scope = Scope.REQUEST

    emoji_pack_repository = provide(EmojiPackRepository)
    import_emoji_pack_use_case = provide(ImportEmojiPackUseCase)
    list_emoji_packs_use_case = provide(ListEmojiPacksUseCase)
    delete_emoji_pack_use_case = provide(DeleteEmojiPackUseCase)


def get_emoji_packs_providers() -> list[Provider]:
    return [EmojiPacksProvider()]
