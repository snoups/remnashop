import base64
import json

from app.modules.oauth.providers.telegram import _decode_id_token_payload


def _build_id_token(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.signature"


def test_decode_id_token_payload_extracts_claims() -> None:
    token = _build_id_token({"id": "987654321", "first_name": "Ada"})

    decoded = _decode_id_token_payload(token)

    assert decoded["id"] == "987654321"
    assert decoded["first_name"] == "Ada"
