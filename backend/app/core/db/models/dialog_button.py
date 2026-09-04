from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import ButtonLinkType, ButtonStyleKind


class DialogButton(BaseSql, TimestampMixin):
    __tablename__ = "dialog_buttons"
    __table_args__ = (
        UniqueConstraint("window_id", "row", "column", name="ux_dialog_buttons_window_row_column"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    window_id: Mapped[int] = mapped_column(
        ForeignKey("dialog_windows.id", ondelete="CASCADE"), index=True
    )
    row: Mapped[int]
    column: Mapped[int]
    text_key: Mapped[str] = mapped_column(String(64))
    icon_custom_emoji_id: Mapped[Optional[str]] = mapped_column(String(32))
    style: Mapped[Optional[ButtonStyleKind]] = mapped_column(String(16))
    visibility_condition: Mapped[Optional[str]] = mapped_column(String(64))
    link_type: Mapped[ButtonLinkType] = mapped_column(String(16))
    action_key: Mapped[Optional[str]] = mapped_column(String(64))
    target_window_key: Mapped[Optional[str]] = mapped_column(String(128))
    url_value: Mapped[Optional[str]] = mapped_column(Text)
    is_hidden: Mapped[bool] = mapped_column(server_default=text("false"))
