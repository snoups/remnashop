from typing import Optional

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import DEFAULT_ALLOWED_EMAIL_DOMAINS
from app.core.db.base import BaseSql
from app.core.db.encrypted_string import EncryptedString
from app.core.db.timestamp import TimestampMixin
from app.core.enums import CaptchaProvider


class CabinetAuthSettings(BaseSql, TimestampMixin):
    __tablename__ = "cabinet_auth_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    telegram_oauth_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    google_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    yandex_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    email_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    restrict_email_domains: Mapped[bool] = mapped_column(default=True, server_default="true")
    allowed_email_domains: Mapped[list[str]] = mapped_column(
        JSONB, default=lambda: list(DEFAULT_ALLOWED_EMAIL_DOMAINS), server_default="[]"
    )
    # guards the anonymous email-code request
    captcha_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    captcha_provider: Mapped[CaptchaProvider] = mapped_column(
        default=CaptchaProvider.TURNSTILE, server_default="TURNSTILE"
    )
    captcha_site_key: Mapped[Optional[str]] = mapped_column(String(255))
    captcha_secret_key: Mapped[Optional[str]] = mapped_column(EncryptedString())
