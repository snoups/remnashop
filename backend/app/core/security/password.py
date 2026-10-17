import asyncio
import hashlib
import hmac
import re
import secrets
import string
from typing import Final

from loguru import logger

PASSWORD_MIN_LENGTH: Final[int] = 24
# bootstrap, admin creation and password change; here rather than in
# core/constants.py, which would import core.security back
PASSWORD_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d).{{{PASSWORD_MIN_LENGTH},}}$"
)

_PASSWORD_ALPHABET: Final[str] = string.ascii_letters + string.digits
_SCRYPT_N: Final[int] = 16384
_SCRYPT_R: Final[int] = 8
_SCRYPT_P: Final[int] = 1
_SCRYPT_DKLEN: Final[int] = 64


def _pepper(password: str, secret: str) -> str:
    return hmac.new(secret.encode(), password.encode(), hashlib.sha256).hexdigest()


def _derive(peppered: str, salt: str) -> str:
    derived = hashlib.scrypt(
        peppered.encode(),
        salt=salt.encode(),
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return derived.hex()


async def hash_password(password: str, secret: str) -> str:
    salt = secrets.token_hex(16)
    # scrypt takes tens of ms of CPU; a thread keeps it off the event loop
    digest = await asyncio.to_thread(_derive, _pepper(password, secret), salt)
    return f"{salt}:{digest}"


async def verify_password(password: str, password_hash: str, secret: str) -> bool:
    salt, separator, expected = password_hash.partition(":")
    if not separator:
        # a hand-edited row or a restored foreign dump: refuse the login, don't fail the request
        logger.warning("Stored password hash is not in the '<salt>:<digest>' format")
        return False
    digest = await asyncio.to_thread(_derive, _pepper(password, secret), salt)
    return hmac.compare_digest(digest, expected)


def generate_password(length: int = PASSWORD_MIN_LENGTH) -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))
