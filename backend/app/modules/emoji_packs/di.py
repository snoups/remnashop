from dishka import Provider, Scope, provide, provide_all

from app.modules.emoji_packs.repository import EmojiPackRepository
from app.modules.emoji_packs.usecases import (
    DeleteEmojiPackUseCase,
    GetEmojiPackAnimationUseCase,
    GetEmojiPackThumbnailUseCase,
    ImportEmojiPackUseCase,
    ListEmojiPacksUseCase,
)


class EmojiPacksProvider(Provider):
    scope = Scope.REQUEST

    emoji_pack_repository = provide(EmojiPackRepository)
    use_cases = provide_all(
        ImportEmojiPackUseCase,
        ListEmojiPacksUseCase,
        DeleteEmojiPackUseCase,
        GetEmojiPackThumbnailUseCase,
        GetEmojiPackAnimationUseCase,
    )


def get_emoji_packs_providers() -> list[Provider]:
    return [EmojiPacksProvider()]
