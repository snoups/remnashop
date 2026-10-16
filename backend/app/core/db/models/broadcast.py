from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import (
    BroadcastCategory,
    BroadcastChannel,
    BroadcastDelivery,
    BroadcastMediaType,
    BroadcastRecipientStatus,
    BroadcastStatus,
    Locale,
)


class Broadcast(BaseSql, TimestampMixin):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[BroadcastStatus] = mapped_column(index=True)
    title: Mapped[Optional[str]] = mapped_column(String(120))
    category: Mapped[BroadcastCategory]
    audience: Mapped[dict[str, Any]] = mapped_column(JSONB)
    default_locale: Mapped[Locale]
    # {locale: {text, button_labels}} — one atomic content bundle per broadcast
    contents: Mapped[dict[str, Any]] = mapped_column(JSONB)
    buttons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    promocode_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("promocodes.id", ondelete="SET NULL")
    )
    post_to_channel: Mapped[bool] = mapped_column(default=False, server_default="false")
    channel_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    channel_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    media_type: Mapped[Optional[BroadcastMediaType]]
    media_content_type: Mapped[Optional[str]] = mapped_column(String(64))
    media_extension: Mapped[Optional[str]] = mapped_column(String(8))
    media_version: Mapped[int] = mapped_column(default=0, server_default="0")
    media_size_bytes: Mapped[Optional[int]]
    media_file_id: Mapped[Optional[str]] = mapped_column(String(255))
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(index=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[Optional[datetime]]
    completed_at: Mapped[Optional[datetime]]
    recall_requested_at: Mapped[Optional[datetime]]
    total_count: Mapped[int] = mapped_column(default=0, server_default="0")
    sent_count: Mapped[int] = mapped_column(default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(default=0, server_default="0")
    blocked_count: Mapped[int] = mapped_column(default=0, server_default="0")
    recalled_count: Mapped[int] = mapped_column(default=0, server_default="0")
    delivery: Mapped[BroadcastDelivery] = mapped_column(
        default=BroadcastDelivery.TELEGRAM, server_default="TELEGRAM"
    )
    email_fallback: Mapped[bool] = mapped_column(default=False, server_default="false")
    # {locale: {subject, html}}, like contents
    email_contents: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")


class BroadcastRecipient(BaseSql):
    __tablename__ = "broadcast_recipients"
    __table_args__ = (
        UniqueConstraint(
            "broadcast_id", "user_id", "channel", name="uq_broadcast_recipients_user_channel"
        ),
        Index("ix_broadcast_recipients_status", "broadcast_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(ForeignKey("broadcasts.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[BroadcastChannel] = mapped_column(
        default=BroadcastChannel.TELEGRAM, server_default="TELEGRAM"
    )
    status: Mapped[BroadcastRecipientStatus]
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    error: Mapped[Optional[str]] = mapped_column(String(255))
    sent_at: Mapped[Optional[datetime]]
    # lease of a deliver batch, so an overlapping batch can't send the row twice
    claimed_until: Mapped[Optional[datetime]]


class BroadcastEmailImage(BaseSql, TimestampMixin):
    __tablename__ = "broadcast_email_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey("broadcasts.id", ondelete="CASCADE"), index=True
    )
    content_type: Mapped[str] = mapped_column(String(32))
    extension: Mapped[str] = mapped_column(String(8))
    size_bytes: Mapped[int]
