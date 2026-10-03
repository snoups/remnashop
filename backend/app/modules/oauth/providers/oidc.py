from typing import Final, Optional, cast

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.core.utils.http import assert_public_https_host

_DISCOVERY_PATH: Final[str] = "/.well-known/openid-configuration"


class OIDCOAuthClient:
    requires_pkce = True

    def __init__(self, issuer_url: str, client_id: str, client_secret: str) -> None:
        self._issuer_url = issuer_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret

    async def _discover(self) -> dict[str, str]:
        # re-checked here, not only on save, to narrow the DNS-rebinding window
        # (assert_public_https_host)
        await assert_public_https_host(self._issuer_url)
        # No redirects: the guard above only vets the issuer's own host, and a
        # redirect would carry this server-side request to an unvetted one
        # (link-local metadata, anything on the internal network). OIDC
        # Discovery serves the document at the issuer itself.
        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.get(f"{self._issuer_url}{_DISCOVERY_PATH}")
            response.raise_for_status()
            try:
                metadata = response.json()
            except ValueError as error:
                raise KeyError("openid-configuration response is not valid JSON") from error
            if not isinstance(metadata, dict):
                raise KeyError("openid-configuration response is not a JSON object")
            return metadata

    async def authorization_url(
        self, redirect_uri: str, state: str, code_verifier: Optional[str]
    ) -> str:
        metadata = await self._discover()
        async with AsyncOAuth2Client(
            self._client_id,
            self._client_secret,
            redirect_uri=redirect_uri,
            scope="openid profile email",
            code_challenge_method="S256",
        ) as client:
            url, _ = client.create_authorization_url(
                metadata["authorization_endpoint"], state=state, code_verifier=code_verifier
            )
            return cast(str, url)

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: Optional[str]
    ) -> tuple[str, Optional[str]]:
        metadata = await self._discover()
        # server-side requests carrying client_secret or the access token
        # (unlike authorization_endpoint, a browser redirect), so a malicious
        # discovery response can't point them off-issuer
        await assert_public_https_host(metadata["token_endpoint"])
        await assert_public_https_host(metadata["userinfo_endpoint"])
        async with AsyncOAuth2Client(
            self._client_id, self._client_secret, redirect_uri=redirect_uri
        ) as client:
            await client.fetch_token(
                metadata["token_endpoint"], code=code, code_verifier=code_verifier
            )
            response = await client.get(metadata["userinfo_endpoint"])
            response.raise_for_status()
            data = response.json()
            return str(data["sub"]), data.get("preferred_username") or data.get("email")
