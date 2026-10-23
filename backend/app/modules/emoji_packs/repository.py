from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.emoji_pack import EmojiPack, EmojiPackItem
from app.modules.emoji_packs.dto import EmojiPackDto, EmojiPackItemDto, FetchedEmojiPack


class EmojiPackRepository:
    # Items are read with explicit selects rather than an ORM relationship:
    # every write here flushes, which expires a loaded collection, and the next
    # read of it would then fire lazy IO outside the async context.
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: EmojiPack, items: list[EmojiPackItem]) -> EmojiPackDto:
        return EmojiPackDto(
            id=row.id,
            set_name=row.set_name,
            title=row.title,
            items=[
                EmojiPackItemDto(
                    custom_emoji_id=item.custom_emoji_id,
                    fallback_emoji=item.fallback_emoji,
                    animation_kind=item.animation_kind,
                )
                for item in items
            ],
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _items_of(self, pack_id: int) -> list[EmojiPackItem]:
        result = await self.session.execute(
            select(EmojiPackItem)
            .where(EmojiPackItem.pack_id == pack_id)
            .order_by(EmojiPackItem.position)
        )
        return list(result.scalars())

    async def list_all(self) -> list[EmojiPackDto]:
        result = await self.session.execute(select(EmojiPack).order_by(EmojiPack.title))
        return [self._to_dto(row, await self._items_of(row.id)) for row in result.scalars()]

    async def upsert(self, data: FetchedEmojiPack) -> EmojiPackDto:
        # Re-importing an existing pack replaces its contents: an owner can add
        # and remove emoji, and a stale entry would resolve to nothing.
        row = await self.session.scalar(
            select(EmojiPack).where(EmojiPack.set_name == data.set_name)
        )
        if row is None:
            row = EmojiPack(set_name=data.set_name)
            self.session.add(row)

        row.title = data.title
        await self.session.flush()
        await self.session.execute(delete(EmojiPackItem).where(EmojiPackItem.pack_id == row.id))

        for position, item in enumerate(data.items):
            self.session.add(
                EmojiPackItem(
                    pack_id=row.id,
                    position=position,
                    custom_emoji_id=item.custom_emoji_id,
                    fallback_emoji=item.fallback_emoji,
                    thumbnail=item.thumbnail,
                    animation=item.animation,
                    animation_kind=item.animation_kind,
                )
            )
        await self.session.flush()
        # The bulk delete above expires the pack row itself, timestamps included.
        await self.session.refresh(row)
        return self._to_dto(row, await self._items_of(row.id))

    async def find_thumbnail(self, custom_emoji_id: str) -> Optional[bytes]:
        return await self.session.scalar(
            select(EmojiPackItem.thumbnail).where(EmojiPackItem.custom_emoji_id == custom_emoji_id)
        )

    async def find_animation(self, custom_emoji_id: str) -> Optional[tuple[bytes, str]]:
        row = (
            await self.session.execute(
                select(EmojiPackItem.animation, EmojiPackItem.animation_kind).where(
                    EmojiPackItem.custom_emoji_id == custom_emoji_id
                )
            )
        ).first()
        if row is None or row.animation is None or row.animation_kind is None:
            return None
        return row.animation, row.animation_kind

    async def delete(self, set_name: str) -> bool:
        row = await self.session.scalar(select(EmojiPack).where(EmojiPack.set_name == set_name))
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True
