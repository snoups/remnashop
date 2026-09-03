from typing import Final, Optional, cast

from authlib.integrations.httpx_client import AsyncOAuth2Client

_AUTHORIZE_ENDPOINT: Final[str] = "https://github.com/login/oauth/authorize"
_TOKEN_ENDPOINT: Final[str] = "https://github.com/login/oauth/access_token"
_USER_ENDPOINT: Final[str] = "https://api.github.com/user"


class GitHubOAuthClient:
    requires_pkce = False

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    async def authorization_url(
        self, redirect_uri: str, state: str, code_verifier: Optional[str]
    ) -> str:
        client = AsyncOAuth2Client(
            self._client_id, self._client_secret, redirect_uri=redirect_uri, scope="read:user"
        )
        url, _ = client.create_authorization_url(_AUTHORIZE_ENDPOINT, state=state)
        return cast(str, url)

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: Optional[str]
    ) -> tuple[str, Optional[str]]:
        async with AsyncOAuth2Client(
            self._client_id,
            self._client_secret,
            redirect_uri=redirect_uri,
        ) as client:
            await client.fetch_token(_TOKEN_ENDPOINT, code=code)
            response = await client.get(_USER_ENDPOINT)
            response.raise_for_status()
            data = response.json()
            return str(data["id"]), data.get("login")
