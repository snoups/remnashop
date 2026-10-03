from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base import BaseSql
from app.core.db.timestamp import NOW_FUNC
from app.core.enums import AdLinkChannel

if TYPE_CHECKING:
    from app.core.db.models.ad_link import AdLink


class AdLinkAttribution(BaseSql):
    __tablename__ = "ad_link_attributions"

    id: Mapped[int] = mapped_column(primary_key=True)
    ad_link_id: Mapped[int] = mapped_column(
        ForeignKey("ad_links.id", ondelete="CASCADE"), index=True
    )
    # one ad link per user, ever: first touch wins, enforced by the DB
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    channel: Mapped[AdLinkChannel] = mapped_column(default=AdLinkChannel.BOT, server_default="BOT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW_FUNC)

    ad_link: Mapped["AdLink"] = relationship(back_populates="attributions")
