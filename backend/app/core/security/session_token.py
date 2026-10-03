import hashlib
import hmac
import secrets


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    # Plain SHA-256, not scrypt: this hashes 256 bits of random entropy, not
    # a low-entropy user password, so a slow hash buys nothing here.
    return hashlib.sha256(token.encode()).hexdigest()


def derive_csrf_token(refresh_token: str, secret: str) -> str:
    # Signed double-submit cookie (OWASP). A plain cookie == header check fails
    # once an attacker can plant a cookie for this domain (sibling-subdomain
    # cookie tossing and the like): they mirror it into the header. The
    # signature ties the value to this refresh token and the server secret.
    return hmac.new(secret.encode(), f"csrf:{refresh_token}".encode(), hashlib.sha256).hexdigest()
