import base64
import hashlib
import hmac
import re
from typing import Final

# The cabinet's word that a subscription link is one it gave a signed-in customer. The public page a
# Mini App deep link opens in the browser reads its link from the address, which anybody can write:
# the catalog vouches for the app's scheme, this for the subscription inside it. The page sends only
# SHA-256 of the link and the signature, never the link, so no log on the way holds a subscription.
#
#   key       = HMAC-SHA256(jwt_secret, KEY_LABEL)   derived: means nothing else signed
#   signature = base64url(HMAC-SHA256(key, SHA-256(utf8(subscription_url))))

KEY_LABEL: Final[bytes] = b"remnashop/connect-handoff/v1"

# 32 bytes as unpadded base64url: 43 characters, the last one carries two zero bits
BASE64URL_32_BYTES: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]")


def _mac(digest: bytes, secret: str) -> bytes:
    key = hmac.new(secret.encode(), KEY_LABEL, hashlib.sha256).digest()
    return hmac.new(key, digest, hashlib.sha256).digest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def sign_subscription_url(subscription_url: str, secret: str) -> str:
    return _b64encode(_mac(hashlib.sha256(subscription_url.encode()).digest(), secret))


def verify_connect_signature(digest: str, signature: str, secret: str) -> bool:
    if not BASE64URL_32_BYTES.fullmatch(digest) or not BASE64URL_32_BYTES.fullmatch(signature):
        return False
    expected = _b64encode(_mac(base64.urlsafe_b64decode(digest + "="), secret))
    return hmac.compare_digest(expected, signature)
