import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.exceptions import PaymentGatewayError
from app.core.utils.time import datetime_now
from app.modules.transactions.gateways.common import (
    compact_json,
    format_moscow,
    format_utc,
    hmac_b64,
    hmac_hex,
    link_expiry,
    link_lifetime,
    load_rsa_public_key,
    md5_hex,
    parse_form,
    parse_json,
    rsa_verify,
    safe_equals,
    signing_json,
    to_decimal,
)
from tests.modules.transactions.gateways.support import make_order


def test_safe_equals_handles_non_ascii() -> None:
    assert safe_equals("абв", "абв") is True
    assert safe_equals("абв", "абг") is False


def test_safe_equals_ignore_case() -> None:
    assert safe_equals("ABCDEF", "abcdef", ignore_case=True) is True
    assert safe_equals("ABCDEF", "abcdef") is False


def test_signing_json_escapes_slashes_like_php() -> None:
    # Heleket's documented example.
    data = {"amount": "20", "currency": "USDT", "network": "tron", "txid": "someTxidWith/Slash"}
    assert signing_json(data, escape_unicode=False) == (
        b'{"amount":"20","currency":"USDT","network":"tron","txid":"someTxidWith\\/Slash"}'
    )


def test_signing_json_unicode_modes() -> None:
    assert signing_json({"c": "т"}, escape_unicode=False) == '{"c":"т"}'.encode()
    assert signing_json({"c": "т"}, escape_unicode=True) == b'{"c":"\\u0442"}'


def test_compact_json_keeps_slashes_and_unicode() -> None:
    assert compact_json({"u": "https://x/т"}) == '{"u":"https://x/т"}'.encode()


def test_digest_helpers() -> None:
    assert hmac_hex("key", b"msg") == (
        "2d93cbc1be167bcb1637a4a23cbff01a7878f0c50ee833954ea5221bb1b8c628"
    )
    assert hmac_hex("key", b"msg", "sha512").startswith("1e4b55b925ccc28ed90d")
    assert hmac_b64("key", b"msg") == "LZPLwb4We8sWN6SiPL/wGnh48MUO6DOVTqUiG7G4xig="
    assert md5_hex("abc") == "900150983cd24fb0d6963f7d28e17f72"


def _rsa_pair() -> tuple[rsa.RSAPrivateKey, str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    der = public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    pem = public_key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, base64.b64encode(der).decode(), pem.decode()


@pytest.mark.parametrize("key_format", ["der", "pem"])
def test_rsa_verify_accepts_der_and_pem_keys(key_format: str) -> None:
    private_key, der_b64, pem = _rsa_pair()
    body = b'{"x":1}'
    signature = base64.b64encode(
        private_key.sign(body, padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    material = f"  {der_b64}\n" if key_format == "der" else pem

    key = load_rsa_public_key(material)

    assert rsa_verify(key, signature, body, hashes.SHA256()) is True
    assert rsa_verify(key, signature, b'{"x":2}', hashes.SHA256()) is False
    assert rsa_verify(key, "not base64!!", body, hashes.SHA256()) is False


def test_load_rsa_public_key_rejects_garbage() -> None:
    with pytest.raises(PaymentGatewayError):
        load_rsa_public_key("bm90IGEga2V5")


def test_parse_json_keeps_key_order_and_rejects_non_objects() -> None:
    assert list(parse_json(b'{"b":1,"a":2}', "X")) == ["b", "a"]
    with pytest.raises(PaymentGatewayError):
        parse_json(b"[1]", "X")
    with pytest.raises(PaymentGatewayError):
        parse_json(b"not json", "X")


def test_parse_form() -> None:
    assert parse_form(b"a=1&b=&c=x%2Fy", "X") == {"a": "1", "b": "", "c": "x/y"}
    with pytest.raises(PaymentGatewayError):
        parse_form(b"\xff\xfe", "X")


def test_to_decimal() -> None:
    assert to_decimal("100.000000") == Decimal("100")
    assert to_decimal(1000.99) == Decimal("1000.99")
    assert to_decimal(None) is None
    assert to_decimal(True) is None
    assert to_decimal("abc") is None
    assert to_decimal("NaN") is None


def test_link_lifetime_units() -> None:
    order = make_order(expires_at=datetime_now() + timedelta(minutes=30, seconds=5))
    assert 1795 <= link_lifetime(order, unit="seconds") <= 1805
    assert link_lifetime(order, unit="minutes") == 30


def test_link_lifetime_clamps() -> None:
    order = make_order(expires_at=datetime_now() + timedelta(minutes=29, seconds=50))
    assert link_lifetime(order, unit="minutes", minimum=30) == 30
    assert link_lifetime(order, unit="seconds", maximum=600) == 600
    expired = make_order(expires_at=datetime_now() - timedelta(minutes=1))
    assert link_lifetime(expired, unit="seconds") == 1


def test_link_expiry_respects_minimum() -> None:
    soon = make_order(expires_at=datetime_now() + timedelta(minutes=5))
    assert link_expiry(soon, minimum_seconds=660) >= datetime_now() + timedelta(seconds=650)
    later = make_order(expires_at=datetime_now() + timedelta(hours=1))
    assert link_expiry(later, minimum_seconds=660) == later.expires_at


def test_format_helpers() -> None:
    moment = datetime(2026, 1, 16, 9, 0, tzinfo=UTC)
    assert format_utc(moment) == "2026-01-16T09:00:00Z"
    assert format_moscow(moment) == "2026-01-16T12:00"
