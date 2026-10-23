import base64
import hashlib
import hmac
from typing import Final, Optional

_PURPOSE: Final[bytes] = b"marketing-unsubscribe"
_MAX_ID_DIGITS: Final[int] = 19


def _key(secret: str) -> bytes:
    # its own key derived from APP_CRYPT_KEY, which also peppers passwords and keys Fernet
    return hmac.new(secret.encode(), b"remnashop/" + _PURPOSE, hashlib.sha256).digest()


def _encode(digest: bytes) -> str:
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _signature(user_id: int, secret: str) -> str:
    return _encode(hmac.new(_key(secret), str(user_id).encode(), hashlib.sha256).digest())


def _legacy_signature(user_id: int, secret: str) -> str:
    # links in emails sent before the derived key; still honoured
    message = _PURPOSE + b":" + str(user_id).encode()
    return _encode(hmac.new(secret.encode(), message, hashlib.sha256).digest())


def unsubscribe_token(user_id: int, secret: str) -> str:
    return f"{user_id}.{_signature(user_id, secret)}"


def read_unsubscribe_token(token: str, secret: str) -> Optional[int]:
    raw_id, _, signature = token.partition(".")
    if not (raw_id.isascii() and raw_id.isdigit() and signature.isascii()):
        return None
    # canonical form only: no leading zeros, bounded length (int() digit limit)
    if not signature or len(raw_id) > _MAX_ID_DIGITS or str(int(raw_id)) != raw_id:
        return None
    user_id = int(raw_id)
    if not any(
        hmac.compare_digest(signature, expected)
        for expected in (_signature(user_id, secret), _legacy_signature(user_id, secret))
    ):
        return None
    return user_id
