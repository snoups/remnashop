import base64
import json
from typing import Any, Optional, cast

from authlib.integrations.httpx_client import AsyncOAuth2Client

_AUTHORIZE_ENDPOINT = "https://oauth.telegram.org/auth"
_TOKEN_ENDPOINT = "https://oauth.telegram.org/token"


def _decode_id_token_payload(id_token: str) -> dict[str, Any]:
    # oauth.telegram.org's token response is fetched server-to-server over TLS
    # with client_secret already authenticating the exchange -- the payload is
    # decoded, not signature-verified, the same choice Remnawave's own
    # reference implementation makes for this same endpoint.
    payload_segment = id_token.split(".")[1]
    padded = payload_segment + "=" * (-len(payload_segment) % 4)
    result: dict[str, Any] = json.loads(base64.urlsafe_b64decode(padded))
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
    ) -> tuple[str, Optional[str]]:
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
            return str(payload["id"]), payload.get("username")
