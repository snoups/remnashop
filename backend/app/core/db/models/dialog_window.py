from typing import Optional

from sqlalchemy import String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import BaseSql
from app.core.db.models.dialog_button import DialogButton
from app.core.db.timestamp import TimestampMixin
from app.core.enums import DialogFlow, DialogWindowKind


class DialogWindow(BaseSql, TimestampMixin):
    __tablename__ = "dialog_windows"
    __table_args__ = (
        UniqueConstraint("key", name="ux_dialog_windows_key"),
        UniqueConstraint("slot", name="ux_dialog_windows_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128))
    kind: Mapped[DialogWindowKind] = mapped_column(String(16))
    flow: Mapped[DialogFlow] = mapped_column(String(16))
    # NULL -- no banner; DEFAULT_BANNER_NAME -- the shared one; anything else --
    # this window's own, named after its key.
    banner_name: Mapped[Optional[str]] = mapped_column(String(160))
    # Editor-only label of a custom window; never shown to bot users.
    name: Mapped[Optional[str]] = mapped_column(String(128))
    is_enabled: Mapped[bool] = mapped_column(server_default=text("true"))
    position: Mapped[int] = mapped_column(server_default=text("0"))
    # Only custom windows hold one; seed windows render through their own
    # hand-written state. Never reused while the window lives, so a user sitting
    # in a custom window doesn't get moved to a different one when its neighbours
    # are created or deleted.
    slot: Mapped[Optional[int]] = mapped_column()
    default_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    buttons: Mapped[list[DialogButton]] = relationship(
        cascade="all, delete-orphan",
        order_by="DialogButton.row, DialogButton.column",
        lazy="selectin",
    )
