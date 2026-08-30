from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import Locale


class ActiveLocale(BaseSql, TimestampMixin):
    __tablename__ = "active_locales"
    __table_args__ = (UniqueConstraint("locale", name="ux_active_locales_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    locale: Mapped[Locale]
