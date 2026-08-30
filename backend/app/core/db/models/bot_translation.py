from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import Locale


class BotTranslation(BaseSql, TimestampMixin):
    __tablename__ = "bot_translations"
    __table_args__ = (
        UniqueConstraint(
            "locale",
            "message_id",
            "attribute_id",
            name="ux_bot_translations_locale_message_attribute",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    locale: Mapped[Locale]
    message_id: Mapped[str] = mapped_column(String(64))
    # "" -- the message's own value, not an attribute. Composite unique index
    # with a NULL column wouldn't treat two such rows as duplicates in
    # Postgres, and we need exactly one row per (locale, message_id, "").
    attribute_id: Mapped[str] = mapped_column(String(64), default="", server_default="")
    value: Mapped[str] = mapped_column(Text())
    default_value: Mapped[str] = mapped_column(Text())
