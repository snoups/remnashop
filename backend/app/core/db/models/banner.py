from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import BannerName, Locale


class Banner(BaseSql, TimestampMixin):
    __tablename__ = "banners"
    __table_args__ = (UniqueConstraint("name", "locale", name="ux_banners_name_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[BannerName]
    locale: Mapped[Locale]
    content_type: Mapped[str] = mapped_column(String(64))
    extension: Mapped[str] = mapped_column(String(8))
    size_bytes: Mapped[int] = mapped_column(Integer())
