from dataclasses import dataclass
from datetime import datetime
from enum import auto
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.core.constants import DEFAULT_ALLOWED_EMAIL_DOMAINS
from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import AccessMode, OAuthProvider, SmtpSecurity, UpperStrEnum


class BotSettingsDto(BaseDto, TimestampMixin):
    token: Optional[SecretStr] = None
    secret_token: Optional[SecretStr] = None
    proxy_url: Optional[SecretStr] = None
    drop_pending_updates: bool = False

    @property
    def is_configured(self) -> bool:
        return self.token is not None and self.secret_token is not None

    @property
    def is_proxy_configured(self) -> bool:
        return self.proxy_url is not None

    @property
    def proxy(self) -> Optional[str]:
        return self.proxy_url.get_secret_value() if self.proxy_url is not None else None


@dataclass(frozen=True, kw_only=True)
class BotStatusDto:
    is_configured: bool
    webhook_url: Optional[str] = None
    pending_update_count: int = 0
    error: Optional[str] = None
    last_error_at: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        return self.webhook_url is not None and self.error is None


@dataclass(frozen=True, kw_only=True)
class UpdateBotSettingsDto:
    token: Optional[str] = None
    secret_token: Optional[str] = None
    drop_pending_updates: Optional[bool] = None


class ShopSettingsDto(BaseDto, TimestampMixin):
    # None = unlimited. The column has no default (see
    # core/db/models/shop_settings.py), so this covers a row that doesn't exist yet.
    max_active_subscriptions: Optional[int] = 3
    device_single_reset_enabled: bool = True
    device_single_reset_cooldown_hours: int = 0
    device_all_reset_enabled: bool = True
    device_all_reset_cooldown_hours: int = 0
    link_reset_enabled: bool = True
    link_reset_cooldown_hours: int = 0


@dataclass(frozen=True, kw_only=True)
class CabinetSettingsDto:
    # the part of the shop settings a customer needs, without admin-only cooldowns
    max_active_subscriptions: Optional[int]
    device_single_reset_enabled: bool
    device_all_reset_enabled: bool
    link_reset_enabled: bool
    bot_username: Optional[str]


@dataclass(frozen=True, kw_only=True)
class UpdateShopSettingsDto:
    # None in max_active_subscriptions means unlimited; fields_set says which
    # fields the caller sent.
    max_active_subscriptions: Optional[int] = None
    device_single_reset_enabled: Optional[bool] = None
    device_single_reset_cooldown_hours: Optional[int] = None
    device_all_reset_enabled: Optional[bool] = None
    device_all_reset_cooldown_hours: Optional[int] = None
    link_reset_enabled: Optional[bool] = None
    link_reset_cooldown_hours: Optional[int] = None
    fields_set: frozenset[str] = frozenset()


class BotCommandDto(BaseDto, TimestampMixin):
    command: str
    sort_order: int = 0
    enabled: bool = True


@dataclass(frozen=True, kw_only=True)
class GetBotCommandsDto:
    # BOT_COMMANDS' own order instead of the stored one, for the "reset order" button
    default_order: bool = False


@dataclass(frozen=True, kw_only=True)
class UpdateBotCommandsDto:
    # (command, enabled) in display order
    commands: list[tuple[str, bool]]


@dataclass(frozen=True, kw_only=True)
class SetBotProxyDto:
    proxy_url: str


class UpdateBotCommandsResultDto(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore")

    commands: list[BotCommandDto]
    telegram_sync_failed: bool = False


class OAuthSettingsDto(BaseDto, TimestampMixin):
    github_client_id: Optional[str] = None
    github_client_secret: Optional[SecretStr] = None
    github_enabled: bool = False
    telegram_client_id: Optional[str] = None
    telegram_client_secret: Optional[SecretStr] = None
    telegram_enabled: bool = False
    google_client_id: Optional[str] = None
    google_client_secret: Optional[SecretStr] = None
    yandex_client_id: Optional[str] = None
    yandex_client_secret: Optional[SecretStr] = None
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[SecretStr] = None
    oidc_display_name: Optional[str] = None
    oidc_enabled: bool = False
    password_login_enabled: bool = True
    passkey_enabled: bool = False
    passkey_rp_id: Optional[str] = None
    passkey_origin: Optional[str] = None

    @property
    def is_github_configured(self) -> bool:
        return self.github_client_id is not None and self.github_client_secret is not None

    @property
    def is_telegram_configured(self) -> bool:
        return self.telegram_client_id is not None and self.telegram_client_secret is not None

    @property
    def is_google_configured(self) -> bool:
        return self.google_client_id is not None and self.google_client_secret is not None

    @property
    def is_yandex_configured(self) -> bool:
        return self.yandex_client_id is not None and self.yandex_client_secret is not None

    @property
    def is_github_usable(self) -> bool:
        return self.is_github_configured and self.github_enabled

    @property
    def is_telegram_usable(self) -> bool:
        return self.is_telegram_configured and self.telegram_enabled

    @property
    def is_oidc_configured(self) -> bool:
        # display_name is the login button's label, so it's required too
        return (
            self.oidc_issuer_url is not None
            and self.oidc_client_id is not None
            and self.oidc_client_secret is not None
            and self.oidc_display_name is not None
        )

    @property
    def is_oidc_usable(self) -> bool:
        return self.is_oidc_configured and self.oidc_enabled

    @property
    def is_passkey_configured(self) -> bool:
        return self.passkey_rp_id is not None and self.passkey_origin is not None

    @property
    def is_passkey_usable(self) -> bool:
        return self.is_passkey_configured and self.passkey_enabled


@dataclass(frozen=True, kw_only=True)
class UpdateOAuthSettingsDto:
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    github_enabled: Optional[bool] = None
    telegram_client_id: Optional[str] = None
    telegram_client_secret: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    yandex_client_id: Optional[str] = None
    yandex_client_secret: Optional[str] = None
    oidc_issuer_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_display_name: Optional[str] = None
    oidc_enabled: Optional[bool] = None
    password_login_enabled: Optional[bool] = None
    passkey_enabled: Optional[bool] = None
    passkey_rp_id: Optional[str] = None
    passkey_origin: Optional[str] = None


class AppearanceSettingsDto(BaseDto, TimestampMixin):
    brand_name: Optional[str] = None
    primary_color: Optional[str] = None
    shader_palette: Optional[list[str]] = None
    shader_enabled: bool = True
    has_logo: bool = False
    has_favicon: bool = False


@dataclass(frozen=True, kw_only=True)
class UpdateAppearanceSettingsDto:
    brand_name: Optional[str] = None
    primary_color: Optional[str] = None
    shader_palette: Optional[list[str]] = None
    shader_enabled: Optional[bool] = None


@dataclass(frozen=True, kw_only=True)
class UploadAppearanceImageDto:
    content_type: str
    data: bytes


class AccessSettingsDto(BaseDto, TimestampMixin):
    mode: AccessMode = AccessMode.PUBLIC
    registration_enabled: bool = True
    payments_enabled: bool = True


@dataclass(frozen=True, kw_only=True)
class UpdateAccessSettingsDto:
    mode: Optional[AccessMode] = None
    registration_enabled: Optional[bool] = None
    payments_enabled: Optional[bool] = None


class EmailSettingsDto(BaseDto, TimestampMixin):
    host: Optional[str] = None
    port: int = 587
    security: SmtpSecurity = SmtpSecurity.STARTTLS
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    from_address: Optional[str] = None
    from_name: Optional[str] = None
    bulk_host: Optional[str] = None
    bulk_port: int = 587
    bulk_security: SmtpSecurity = SmtpSecurity.STARTTLS
    bulk_username: Optional[str] = None
    bulk_password: Optional[SecretStr] = None
    bulk_from_address: Optional[str] = None
    bulk_from_name: Optional[str] = None
    bulk_rate_per_minute: int = 60

    @property
    def is_configured(self) -> bool:
        return self.host is not None and self.from_address is not None

    @property
    def is_password_set(self) -> bool:
        return self.password is not None

    @property
    def is_bulk_configured(self) -> bool:
        return self.bulk_host is not None and self.bulk_from_address is not None

    @property
    def is_bulk_password_set(self) -> bool:
        return self.bulk_password is not None

    def profile(self, *, bulk: bool) -> "SmtpProfileDto":
        if bulk and self.is_bulk_configured:
            return SmtpProfileDto(
                host=self.bulk_host,
                port=self.bulk_port,
                security=self.bulk_security,
                username=self.bulk_username,
                password=self.bulk_password,
                from_address=self.bulk_from_address,
                from_name=self.bulk_from_name,
                is_bulk=True,
            )
        return SmtpProfileDto(
            host=self.host,
            port=self.port,
            security=self.security,
            username=self.username,
            password=self.password,
            from_address=self.from_address,
            from_name=self.from_name,
            is_bulk=False,
        )


@dataclass(frozen=True, kw_only=True)
class SmtpProfileDto:
    host: Optional[str]
    port: int
    security: SmtpSecurity
    username: Optional[str]
    password: Optional[SecretStr]
    from_address: Optional[str]
    from_name: Optional[str]
    is_bulk: bool

    @property
    def is_configured(self) -> bool:
        return self.host is not None and self.from_address is not None


@dataclass(frozen=True, kw_only=True)
class UpdateEmailSettingsDto:
    host: Optional[str] = None
    port: Optional[int] = None
    security: Optional[SmtpSecurity] = None
    username: Optional[str] = None
    password: Optional[str] = None
    from_address: Optional[str] = None
    from_name: Optional[str] = None
    bulk_host: Optional[str] = None
    bulk_port: Optional[int] = None
    bulk_security: Optional[SmtpSecurity] = None
    bulk_username: Optional[str] = None
    bulk_password: Optional[str] = None
    bulk_from_address: Optional[str] = None
    bulk_from_name: Optional[str] = None
    bulk_rate_per_minute: Optional[int] = None


class CabinetAuthSettingsDto(BaseDto, TimestampMixin):
    telegram_enabled: bool = False
    telegram_oauth_enabled: bool = False
    google_enabled: bool = False
    yandex_enabled: bool = False
    email_enabled: bool = False
    restrict_email_domains: bool = True
    allowed_email_domains: list[str] = Field(
        default_factory=lambda: list(DEFAULT_ALLOWED_EMAIL_DOMAINS)
    )

    def is_oauth_enabled(self, provider: OAuthProvider) -> bool:
        if provider is OAuthProvider.TELEGRAM:
            return self.telegram_oauth_enabled
        if provider is OAuthProvider.GOOGLE:
            return self.google_enabled
        if provider is OAuthProvider.YANDEX:
            return self.yandex_enabled
        return False


@dataclass(frozen=True, kw_only=True)
class UpdateCabinetAuthSettingsDto:
    telegram_enabled: Optional[bool] = None
    telegram_oauth_enabled: Optional[bool] = None
    google_enabled: Optional[bool] = None
    yandex_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    restrict_email_domains: Optional[bool] = None
    allowed_email_domains: Optional[list[str]] = None


class BotRequirementsDto(BaseDto, TimestampMixin):
    channel_required: bool = False
    channel_id: Optional[int] = None
    channel_url: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class UpdateBotRequirementsDto:
    # full replace: None clears a field
    channel_required: bool
    channel_id: Optional[int]
    channel_url: Optional[str]


@dataclass(frozen=True, kw_only=True)
class AppearanceImageDto:
    data: bytes
    content_type: str


class BotStatusKind(UpperStrEnum):
    STARTED = auto()
    STOPPED = auto()
    WEBHOOK_FAILED = auto()
    CHANNEL_CHECK_FAILED = auto()


@dataclass(frozen=True, kw_only=True)
class ReportBotStatusDto:
    kind: BotStatusKind
    detail: Optional[str] = None
    channel_id: Optional[int] = None
