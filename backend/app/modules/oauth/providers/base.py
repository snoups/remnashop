from dataclasses import dataclass
from typing import Final, Optional, Protocol

import httpx
import jwt
from authlib.integrations.base_client.errors import OAuthError

from app.core.enums import OAuthProvider
from app.core.exceptions import ValidationError

# What fetch_identity() can raise when the provider round-trip goes wrong: a
# rejected/expired code (OAuthError), a non-2xx or unreachable provider (httpx),
# a response missing the claims we index into (KeyError), a malformed id_token
# (PyJWTError), or the issuer/redirect resolving to a non-public host
# (ValidationError, from the SSRF guard).
OAUTH_EXCHANGE_ERRORS: Final[tuple[type[Exception], ...]] = (
    OAuthError,
    httpx.HTTPError,
    KeyError,
    jwt.PyJWTError,
    ValidationError,
)

# no dashboard enable flag; usable only for cabinet sign-in
CABINET_ONLY_PROVIDERS: Final[frozenset[OAuthProvider]] = frozenset(
    {OAuthProvider.GOOGLE, OAuthProvider.YANDEX}
)


@dataclass(frozen=True)
class OAuthProfile:
    external_id: str
    login: Optional[str]
    name: Optional[str] = None
    email: Optional[str] = None
    email_verified: bool = False
    language: Optional[str] = None


class OAuthProviderClient(Protocol):
    requires_pkce: bool

    async def authorization_url(
        self, redirect_uri: str, state: str, code_verifier: Optional[str]
    ) -> str: ...

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: Optional[str]
    ) -> OAuthProfile: ...


def build_redirect_uri(domain: str, provider: OAuthProvider) -> str:
    return f"https://{domain}/oauth2/callback/{provider.value.lower()}"


def build_cabinet_redirect_uri(cabinet_url: str, provider: OAuthProvider) -> str:
    return f"{cabinet_url.rstrip('/')}/login/callback/{provider.value.lower()}"
