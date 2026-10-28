import base64
import hashlib
import hmac

import pytest

from app.modules.users import unsubscribe_token
from app.modules.users.unsubscribe import read_unsubscribe_token

SECRET = "k" * 32


def test_roundtrip() -> None:
    assert read_unsubscribe_token(unsubscribe_token(42, SECRET), SECRET) == 42


_SIG_42 = unsubscribe_token(42, SECRET).split(".", 1)[1]


@pytest.mark.parametrize(
    "token",
    [
        "",
        "42",
        "42.",
        "x.abc",
        "42.AAAA",
        "-1.abc",
        "².x",
        f"042.{_SIG_42}",
        "42.é",
        "9" * 5000 + ".x",
        f"٤٢.{_SIG_42}",
    ],
)
def test_garbage(token: str) -> None:
    assert read_unsubscribe_token(token, SECRET) is None


def test_other_user_signature_rejected() -> None:
    sig = unsubscribe_token(42, SECRET).split(".", 1)[1]
    assert read_unsubscribe_token(f"43.{sig}", SECRET) is None


def test_other_secret_rejected() -> None:
    assert read_unsubscribe_token(unsubscribe_token(42, SECRET), "z" * 32) is None


def test_a_link_signed_before_the_derived_key_still_unsubscribes() -> None:
    secret = "crypt-key"
    legacy = hmac.new(secret.encode(), b"marketing-unsubscribe:42", hashlib.sha256).digest()
    token = f"42.{base64.urlsafe_b64encode(legacy).rstrip(b'=').decode()}"

    assert read_unsubscribe_token(token, secret) == 42
    # fresh links sign with the derived key, not the crypt key
    assert unsubscribe_token(42, secret) != token
