from typing import Optional

from sqlalchemy import ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class EmojiPack(BaseSql, TimestampMixin):
    __tablename__ = "emoji_packs"
    __table_args__ = (UniqueConstraint("set_name", name="ux_emoji_packs_set_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # the name in t.me/addemoji/<set_name>, what getStickerSet takes
    set_name: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(128))


class EmojiPackItem(BaseSql, TimestampMixin):
    __tablename__ = "emoji_pack_items"
    __table_args__ = (
        UniqueConstraint("custom_emoji_id", name="ux_emoji_pack_items_custom_emoji_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pack_id: Mapped[int] = mapped_column(
        ForeignKey("emoji_packs.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    custom_emoji_id: Mapped[str] = mapped_column(String(32))
    # The plain emoji Telegram shows in place of this one; it is also what the
    # picker renders, and what a button stores when the admin picks a standard
    # emoji instead of a premium one.
    fallback_emoji: Mapped[str] = mapped_column(String(16))
    # the static .webp Telegram renders for this emoji, the only form a browser
    # can draw; deferred, a pack listing has no use for the bytes
    thumbnail: Mapped[Optional[bytes]] = mapped_column(LargeBinary(), deferred=True)
    # The animation itself: gzipped lottie (.tgs) or .webm, stored verbatim.
    animation: Mapped[Optional[bytes]] = mapped_column(LargeBinary(), deferred=True)
    animation_kind: Mapped[Optional[str]] = mapped_column(String(8))
