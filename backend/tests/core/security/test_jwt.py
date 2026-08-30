import time

import jwt as pyjwt
import pytest

from app.core.security.jwt import create_access_token, decode_access_token


def test_create_and_decode_roundtrip() -> None:
    token = create_access_token(user_id=42, session_id=7, secret="test-secret")

    payload = decode_access_token(token, "test-secret")

    assert payload["sub"] == "42"
    assert payload["sid"] == 7
    assert payload["exp"] > int(time.time())


def test_decode_rejects_wrong_secret() -> None:
    token = create_access_token(user_id=1, session_id=1, secret="secret-a")

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token(token, "secret-b")


def test_decode_rejects_tampered_token() -> None:
    token = create_access_token(user_id=1, session_id=1, secret="test-secret")

    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token(token + "tampered", "test-secret")


def test_decode_raises_key_error_on_pre_migration_token_missing_sid() -> None:
    # Simulates a JWT issued before this change (no `sid` claim) -- get_current_actor
    # (Task 7) relies on this raising KeyError when the caller reads payload["sid"].
    old_style_payload = {"sub": "1", "exp": int(time.time()) + 900}
    token = pyjwt.encode(old_style_payload, "test-secret", algorithm="HS256")

    payload = decode_access_token(token, "test-secret")

    with pytest.raises(KeyError):
        _ = payload["sid"]
