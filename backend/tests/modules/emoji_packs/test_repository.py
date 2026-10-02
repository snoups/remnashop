from app.modules.emoji_packs.dto import EmojiPackItemDto, FetchedEmojiPack
from app.modules.emoji_packs.repository import EmojiPackRepository


def _pack(*pairs: tuple[str, str], title: str = "Meme Emoji") -> FetchedEmojiPack:
    return FetchedEmojiPack(
        set_name="MemeEmoji",
        title=title,
        items=[
            EmojiPackItemDto(custom_emoji_id=emoji_id, fallback_emoji=glyph)
            for emoji_id, glyph in pairs
        ],
    )


async def test_upsert_stores_items_in_order(emoji_pack_repository: EmojiPackRepository) -> None:
    pack = await emoji_pack_repository.upsert(_pack(("1", "a"), ("2", "b")))
    assert [item.custom_emoji_id for item in pack.items] == ["1", "2"]


async def test_reimport_replaces_the_previous_contents(
    emoji_pack_repository: EmojiPackRepository,
) -> None:
    # An owner can add and remove emoji in their pack, so a stale entry would
    # keep resolving to an id the set no longer has.
    await emoji_pack_repository.upsert(_pack(("1", "a"), ("2", "b")))
    pack = await emoji_pack_repository.upsert(_pack(("2", "b"), ("3", "c"), title="Renamed"))
    assert pack.title == "Renamed"
    assert [item.custom_emoji_id for item in pack.items] == ["2", "3"]


async def test_delete_reports_whether_anything_was_there(
    emoji_pack_repository: EmojiPackRepository,
) -> None:
    await emoji_pack_repository.upsert(_pack(("1", "a")))
    assert await emoji_pack_repository.delete("MemeEmoji") is True
    assert await emoji_pack_repository.delete("MemeEmoji") is False
