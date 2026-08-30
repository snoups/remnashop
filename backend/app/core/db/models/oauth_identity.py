from typing import Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import OAuthProvider


class OAuthIdentity(BaseSql, TimestampMixin):
    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider", "external_id", name="ux_oauth_identities_provider_external_id"
        ),
        UniqueConstraint("user_id", "provider", name="ux_oauth_identities_user_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[OAuthProvider]
    external_id: Mapped[str] = mapped_column(String(255))
    external_login: Mapped[Optional[str]] = mapped_column(String(255))
