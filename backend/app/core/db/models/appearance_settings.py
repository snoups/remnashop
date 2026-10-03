from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin


class AppearanceSettings(BaseSql, TimestampMixin):
    __tablename__ = "appearance_settings"

    # Single row, always id=1 -- core/db/singleton.py's get_or_create_singleton.
    id: Mapped[int] = mapped_column(primary_key=True)

    brand_name: Mapped[Optional[str]] = mapped_column(String(64))
    primary_color: Mapped[Optional[str]] = mapped_column(String(7))
    # 4 hex colors [base, amplitude, frequency, phase] -- the shader's
    # cosine-gradient palette, always read/written as one unit, never
    # queried column-by-column.
    shader_palette: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    shader_enabled: Mapped[bool] = mapped_column(Boolean(), default=True, server_default="true")

    logo_content_type: Mapped[Optional[str]] = mapped_column(String(32))
    logo_extension: Mapped[Optional[str]] = mapped_column(String(8))
    favicon_content_type: Mapped[Optional[str]] = mapped_column(String(32))
    favicon_extension: Mapped[Optional[str]] = mapped_column(String(8))
