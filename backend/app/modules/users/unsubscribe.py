import base64
import hashlib
import hmac
from typing import Final, Optional

_PURPOSE: Final[bytes] = b"marketing-unsubscribe"
_MAX_ID_DIGITS: Final[int] = 19


def _signature(user_id: int, secret: str) -> str:
    digest = hmac.new(
        secret.encode(), _PURPOSE + b":" + str(user_id).encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


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
    if not hmac.compare_digest(signature, _signature(user_id, secret)):
        return None
    return user_id
