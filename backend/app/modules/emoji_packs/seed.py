import json
from pathlib import Path

from app.modules.emoji_packs.dto import EmojiPackItemDto, FetchedEmojiPack
from app.modules.emoji_packs.repository import EmojiPackRepository


async def ensure_builtin_emoji_packs_seeded(
    emoji_pack_repository: EmojiPackRepository, assets_dir: Path
) -> None:
    # A snapshot of each pack under assets/emoji_packs/<set_name>/: a fresh
    # install has no bot token to fetch one with. Re-importing a pack from
    # the dashboard refreshes it from Telegram.
    existing = {pack.set_name for pack in await emoji_pack_repository.list_all()}
    for manifest_path in sorted((assets_dir / "emoji_packs").glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["set_name"] in existing:
            continue
        items = []
        for item in manifest["items"]:
            artwork = manifest_path.parent / f"{item['custom_emoji_id']}.webp"
            items.append(
                EmojiPackItemDto(
                    custom_emoji_id=item["custom_emoji_id"],
                    fallback_emoji=item["fallback_emoji"],
                    thumbnail=artwork.read_bytes() if artwork.exists() else None,
                )
            )
        await emoji_pack_repository.upsert(
            FetchedEmojiPack(set_name=manifest["set_name"], title=manifest["title"], items=items)
        )
