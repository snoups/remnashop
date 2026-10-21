from typing import Any, Final, Optional, cast

import jwt
from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.modules.oauth.providers.base import OAuthProfile

_AUTHORIZE_ENDPOINT: Final[str] = "https://oauth.telegram.org/auth"
_TOKEN_ENDPOINT: Final[str] = "https://oauth.telegram.org/token"


def _decode_id_token_payload(id_token: str) -> dict[str, Any]:
    # the token response comes server-to-server over TLS, authenticated by
    # client_secret, so the payload is decoded without a signature check
    result: dict[str, Any] = jwt.decode(id_token, options={"verify_signature": False})
    return result


class TelegramOAuthClient:
    requires_pkce = True

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    async def authorization_url(
        self, redirect_uri: str, state: str, code_verifier: Optional[str]
    ) -> str:
        client = AsyncOAuth2Client(
            self._client_id,
            self._client_secret,
            redirect_uri=redirect_uri,
            scope="openid profile",
            code_challenge_method="S256",
        )
        url, _ = client.create_authorization_url(
            _AUTHORIZE_ENDPOINT, state=state, code_verifier=code_verifier
        )
        return cast(str, url)

    async def fetch_identity(
        self, redirect_uri: str, code: str, code_verifier: Optional[str]
    ) -> OAuthProfile:
        async with AsyncOAuth2Client(
            self._client_id,
            self._client_secret,
            redirect_uri=redirect_uri,
        ) as client:
            token = await client.fetch_token(
                _TOKEN_ENDPOINT,
                code=code,
                code_verifier=code_verifier,
            )
            payload = _decode_id_token_payload(token["id_token"])
            return OAuthProfile(
                external_id=str(payload["id"]),
                login=payload.get("username"),
                name=payload.get("name"),
                language=payload.get("locale"),
            )
