from typing import Final, Optional

from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.modules.oauth.providers.base import OAuthProfile, build_authorization_url

_AUTHORIZE_ENDPOINT: Final[str] = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT: Final[str] = "https://oauth2.googleapis.com/token"
_USERINFO_ENDPOINT: Final[str] = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthClient:
    requires_pkce = True

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    async def authorization_url(
        self, redirect_uri: str, state: str, code_verifier: Optional[str]
    ) -> str:
        return await build_authorization_url(
            client_id=self._client_id,
            client_secret=self._client_secret,
            endpoint=_AUTHORIZE_ENDPOINT,
            scope="openid email profile",
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=code_verifier,
        )

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: Optional[str]
    ) -> OAuthProfile:
        async with AsyncOAuth2Client(
            self._client_id, self._client_secret, redirect_uri=redirect_uri
        ) as client:
            await client.fetch_token(_TOKEN_ENDPOINT, code=code, code_verifier=code_verifier)
            response = await client.get(_USERINFO_ENDPOINT)
            response.raise_for_status()
            data = response.json()
        return OAuthProfile(
            external_id=str(data["sub"]),
            login=data.get("email"),
            name=data.get("name"),
            email=data.get("email"),
            email_verified=data.get("email_verified") is True,
            language=data.get("locale"),
        )
