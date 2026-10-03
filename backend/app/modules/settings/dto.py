from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, ConfigDict, SecretStr

from app.core.dto import BaseDto, TimestampMixin


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
class UpdateShopSettingsDto:
    # Full replace, not a partial patch: None in max_active_subscriptions means
    # unlimited, not "leave unchanged".
    max_active_subscriptions: Optional[int]
    device_single_reset_enabled: bool
    device_single_reset_cooldown_hours: int
    device_all_reset_enabled: bool
    device_all_reset_cooldown_hours: int
    link_reset_enabled: bool
    link_reset_cooldown_hours: int


class BotCommandDto(BaseDto, TimestampMixin):
    command: str
    sort_order: int = 0
    enabled: bool = True


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
    def is_github_usable(self) -> bool:
        return self.is_github_configured and self.github_enabled

    @property
    def is_telegram_usable(self) -> bool:
        return self.is_telegram_configured and self.telegram_enabled

    @property
    def is_oidc_configured(self) -> bool:
        # display_name is required alongside the credentials -- without it the
        # login button has nothing to render as its label.
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
