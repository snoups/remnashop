from sqlalchemy import Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import Locale


class ActiveLocale(BaseSql, TimestampMixin):
    __tablename__ = "active_locales"
    __table_args__ = (
        UniqueConstraint("locale", name="ux_active_locales_locale"),
        # at most one default; being a row here keeps it active
        Index(
            "ux_active_locales_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    locale: Mapped[Locale]
    is_default: Mapped[bool] = mapped_column(default=False, server_default="false")
