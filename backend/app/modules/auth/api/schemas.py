from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import LOGIN_PATTERN
from app.core.security import PASSWORD_MIN_LENGTH, PASSWORD_PATTERN


class BootstrapRequest(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: str

    @field_validator("login")
    @classmethod
    def validate_login(cls, value: str) -> str:
        if not LOGIN_PATTERN.match(value):
            raise ValueError(
                "Login may only contain Latin letters, digits, dots, underscores, and hyphens"
            )
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not PASSWORD_PATTERN.match(value):
            raise ValueError(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters long and contain "
                "an uppercase letter, a lowercase letter, and a digit"
            )
        return value


class LoginRequest(BaseModel):
    login: str
    password: str


class AuthResponse(BaseModel):
    id: int
    login: str
    role: str
    access_token: str


class StatusResponse(BaseModel):
    is_login_allowed: bool
    is_register_allowed: bool
    oauth_providers: dict[str, bool]
    oidc_display_name: Optional[str] = None
    is_password_login_enabled: bool


class OAuthAuthorizeResponse(BaseModel):
    authorization_url: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


class OAuthIdentityResponse(BaseModel):
    provider: str
    external_login: Optional[str] = None


class RefreshResponse(BaseModel):
    access_token: str


class SessionResponse(BaseModel):
    id: int
    ip_address: str
    user_agent: Optional[str] = None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
