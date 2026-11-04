from app.core.constants import ASSETS_DIR
from app.modules.emoji_packs.repository import EmojiPackRepository
from app.modules.emoji_packs.seed import ensure_builtin_emoji_packs_seeded


async def test_builtin_pack_is_seeded_once_with_its_artwork(
    emoji_pack_repository: EmojiPackRepository,
) -> None:
    await ensure_builtin_emoji_packs_seeded(emoji_pack_repository, ASSETS_DIR)
    await ensure_builtin_emoji_packs_seeded(emoji_pack_repository, ASSETS_DIR)

    (pack,) = await emoji_pack_repository.list_all()
    assert pack.set_name == "lucide_dev"
    assert len(pack.items) == 199
    first = pack.items[0].custom_emoji_id
    assert await emoji_pack_repository.find_thumbnail(first) is not None
