import base64
import json

import pytest

from app.modules.oauth import OAUTH_EXCHANGE_ERRORS
from app.modules.oauth.providers.telegram import _decode_id_token_payload


def _build_id_token(payload: object) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.c2ln"


def test_decode_id_token_payload_extracts_claims() -> None:
    token = _build_id_token({"id": "987654321", "first_name": "Ada"})

    decoded = _decode_id_token_payload(token)

    assert decoded["id"] == "987654321"
    assert decoded["first_name"] == "Ada"


@pytest.mark.parametrize(
    "token",
    ["no-dots", "a.@@@.c", _build_id_token([1]), "eyJhbGciOiJub25lIn0.bm90IGpzb24.c2ln"],
    ids=["no-segments", "bad-base64", "not-an-object", "not-json"],
)
def test_malformed_id_token_raises_an_exchange_error(token: str) -> None:
    with pytest.raises(OAUTH_EXCHANGE_ERRORS):
        _decode_id_token_payload(token)
