from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.encrypted_string import EncryptedString
from app.core.db.timestamp import TimestampMixin


class OAuthSettings(BaseSql, TimestampMixin):
    __tablename__ = "oauth_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    github_client_id: Mapped[Optional[str]] = mapped_column(EncryptedString())
    github_client_secret: Mapped[Optional[str]] = mapped_column(EncryptedString())
    telegram_client_id: Mapped[Optional[str]] = mapped_column(EncryptedString())
    telegram_client_secret: Mapped[Optional[str]] = mapped_column(EncryptedString())
    google_client_id: Mapped[Optional[str]] = mapped_column(EncryptedString())
    google_client_secret: Mapped[Optional[str]] = mapped_column(EncryptedString())
    yandex_client_id: Mapped[Optional[str]] = mapped_column(EncryptedString())
    yandex_client_secret: Mapped[Optional[str]] = mapped_column(EncryptedString())
    oidc_client_id: Mapped[Optional[str]] = mapped_column(EncryptedString())
    oidc_client_secret: Mapped[Optional[str]] = mapped_column(EncryptedString())

    github_enabled: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    telegram_enabled: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    oidc_enabled: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    password_login_enabled: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="true"
    )
    # a migrated owner without credentials: the next bootstrap sets them on that row
    owner_claim_pending: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="false"
    )

    passkey_enabled: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    # not secrets, like oidc_issuer_url/oidc_display_name above
    passkey_rp_id: Mapped[Optional[str]] = mapped_column(String(255))
    passkey_origin: Mapped[Optional[str]] = mapped_column(String(512))

    # not secrets: the browser sees both (redirect target, login button label)
    oidc_issuer_url: Mapped[Optional[str]] = mapped_column(String(512))
    oidc_display_name: Mapped[Optional[str]] = mapped_column(String(100))
