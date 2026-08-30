from typing import Final, Optional, Protocol

import httpx
from authlib.integrations.base_client.errors import OAuthError

from app.core.enums import OAuthProvider
from app.core.exceptions import ValidationError

# What fetch_identity() can raise when the provider round-trip goes wrong: a
# rejected/expired code (OAuthError), a non-2xx or unreachable provider (httpx),
# a response missing the claims we index into (KeyError), or the issuer/redirect
# resolving to a non-public host (ValidationError, from the SSRF guard).
OAUTH_EXCHANGE_ERRORS: Final[tuple[type[Exception], ...]] = (
    OAuthError,
    httpx.HTTPError,
    KeyError,
    ValidationError,
)


class OAuthProviderClient(Protocol):
    requires_pkce: bool

    async def authorization_url(
        self, redirect_uri: str, state: str, code_verifier: Optional[str]
    ) -> str: ...

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: Optional[str]
    ) -> tuple[str, Optional[str]]: ...


def build_redirect_uri(domain: str, provider: OAuthProvider) -> str:
    return f"https://{domain}/oauth2/callback/{provider.value.lower()}"
