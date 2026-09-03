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
    # Signed double-submit cookie (OWASP), not a plain one: a plain
    # cookie==header check only holds if an attacker can never plant a cookie
    # for this domain on the victim's browser (sibling-subdomain cookie
    # tossing, a misconfigured related app sharing the registrable domain,
    # response splitting elsewhere) -- if they can, they mirror their planted
    # value into the header too and the check passes. Signing ties the
    # cookie's value to this specific refresh token, so a forged pair still
    # can't pass without this server secret.
    return hmac.new(secret.encode(), f"csrf:{refresh_token}".encode(), hashlib.sha256).hexdigest()
