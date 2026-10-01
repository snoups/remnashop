import base64
import binascii
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Literal, Optional
from urllib.parse import parse_qs

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from app.core.exceptions import PaymentGatewayError
from app.core.utils.time import datetime_now
from app.modules.transactions.dto import TransactionDto

PROVIDER_API_TIMEOUT_S: Final[float] = 8.0
_MOSCOW: Final[timezone] = timezone(timedelta(hours=3))


def safe_equals(left: str, right: str, *, ignore_case: bool = False) -> bool:
    if ignore_case:
        left, right = left.lower(), right.lower()
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def hmac_hex(key: str, message: bytes, digest: str = "sha256") -> str:
    return hmac.new(key.encode("utf-8"), message, digest).hexdigest()


def hmac_b64(key: str, message: bytes, digest: str = "sha256") -> str:
    raw = hmac.new(key.encode("utf-8"), message, digest).digest()
    return base64.b64encode(raw).decode("ascii")


def md5_hex(message: str) -> str:
    return hashlib.md5(message.encode("utf-8")).hexdigest()


def signing_json(data: Any, *, escape_unicode: bool) -> bytes:
    # PHP json_encode: compact, "/" escaped; non-ASCII escaped unless
    # JSON_UNESCAPED_UNICODE.
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=escape_unicode)
    return text.replace("/", "\\/").encode("utf-8")


def compact_json(data: Any) -> bytes:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_rsa_public_key(material: str) -> RSAPublicKey:
    text = material.strip()
    try:
        if "BEGIN" in text:
            key = serialization.load_pem_public_key(text.encode("ascii"))
        else:
            key = serialization.load_der_public_key(base64.b64decode(text))
    except (ValueError, binascii.Error, UnsupportedAlgorithm) as error:
        raise PaymentGatewayError("Malformed RSA public key") from error
    if not isinstance(key, RSAPublicKey):
        raise PaymentGatewayError("Public key is not an RSA key")
    return key


def rsa_verify(
    key: RSAPublicKey, signature_b64: str, message: bytes, algorithm: hashes.HashAlgorithm
) -> bool:
    try:
        signature = base64.b64decode(signature_b64.strip(), validate=True)
        key.verify(signature, message, padding.PKCS1v15(), algorithm)
    except (InvalidSignature, binascii.Error, ValueError):
        return False
    return True


def parse_json(body: bytes, gateway: str) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError) as error:
        raise PaymentGatewayError(f"Malformed {gateway} webhook") from error
    if not isinstance(data, dict):
        raise PaymentGatewayError(f"Malformed {gateway} webhook")
    return data


def parse_form(body: bytes, gateway: str) -> dict[str, str]:
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError as error:
        raise PaymentGatewayError(f"Malformed {gateway} webhook") from error
    return {key: values[0] for key, values in parsed.items()}


def to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def link_lifetime(
    order: TransactionDto,
    *,
    unit: Literal["seconds", "minutes"],
    minimum: int = 1,
    maximum: Optional[int] = None,
) -> int:
    remaining = (order.expires_at - datetime_now()).total_seconds()
    value = int(remaining) if unit == "seconds" else int(remaining // 60)
    value = max(value, minimum)
    return min(value, maximum) if maximum is not None else value


def link_expiry(order: TransactionDto, *, minimum_seconds: int = 0) -> datetime:
    return max(order.expires_at, datetime_now() + timedelta(seconds=minimum_seconds))


def format_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_moscow(moment: datetime) -> str:
    return moment.astimezone(_MOSCOW).strftime("%Y-%m-%dT%H:%M")
