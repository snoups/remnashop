from typing import Final, Optional

from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.modules.oauth.providers.base import OAuthProfile, build_authorization_url

_AUTHORIZE_ENDPOINT: Final[str] = "https://oauth.yandex.ru/authorize"
_TOKEN_ENDPOINT: Final[str] = "https://oauth.yandex.ru/token"
_INFO_ENDPOINT: Final[str] = "https://login.yandex.ru/info?format=json"


class YandexOAuthClient:
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
            scope="login:info login:email",
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
            token = await client.fetch_token(
                _TOKEN_ENDPOINT, code=code, code_verifier=code_verifier
            )
            response = await client.get(
                _INFO_ENDPOINT, headers={"Authorization": f"OAuth {token['access_token']}"}
            )
            response.raise_for_status()
            data = response.json()
        email = data.get("default_email")
        # Yandex ID hands out only an address it has confirmed as the account's default
        return OAuthProfile(
            external_id=str(data["id"]),
            login=data.get("login"),
            name=data.get("real_name") or data.get("display_name"),
            email=email,
            email_verified=email is not None,
        )
