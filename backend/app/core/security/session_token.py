import hashlib
import secrets


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    # Plain SHA-256, not scrypt: this hashes 256 bits of random entropy, not
    # a low-entropy user password, so a slow hash buys nothing here.
    return hashlib.sha256(token.encode()).hexdigest()
