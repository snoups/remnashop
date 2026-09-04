from typing import Optional

from sqlalchemy import String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import BaseSql
from app.core.db.models.dialog_button import DialogButton
from app.core.db.timestamp import TimestampMixin
from app.core.enums import BannerName, DialogFlow, DialogWindowKind


class DialogWindow(BaseSql, TimestampMixin):
    __tablename__ = "dialog_windows"
    __table_args__ = (UniqueConstraint("key", name="ux_dialog_windows_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128))
    kind: Mapped[DialogWindowKind] = mapped_column(String(16))
    flow: Mapped[DialogFlow] = mapped_column(String(16))
    banner_name: Mapped[Optional[BannerName]] = mapped_column(String(32))
    is_enabled: Mapped[bool] = mapped_column(server_default=text("true"))
    position: Mapped[int] = mapped_column(server_default=text("0"))
    default_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    buttons: Mapped[list[DialogButton]] = relationship(
        cascade="all, delete-orphan",
        order_by="DialogButton.row, DialogButton.column",
        lazy="selectin",
    )
