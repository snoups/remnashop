import secrets
import time
from typing import Final, Literal, Optional, TypedDict, cast

import jwt

from app.core.constants import TTL_15M


class AccessTokenPayload(TypedDict):
    sub: str
    sid: int
    exp: int


def create_access_token(user_id: int, session_id: int, secret: str) -> str:
    payload: AccessTokenPayload = {
        "sub": str(user_id),
        "sid": session_id,
        "exp": int(time.time()) + TTL_15M,
    }
    return jwt.encode(dict(payload), secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> AccessTokenPayload:
    return cast(AccessTokenPayload, jwt.decode(token, secret, algorithms=["HS256"]))


# A dashboard session trades for a seconds-long one-time ticket, the docs
# page trades that for a cookie scoped to the docs path.
_DOCS_TOKEN_ISSUER: Final[str] = "remnashop-docs"
DocsTokenScope = Literal["ott", "access"]


def create_docs_token(scope: DocsTokenScope, ttl: int, secret: str, session_id: int) -> str:
    # jti: two tickets issued in the same second must still differ, since a
    # ticket is consumed by its hash; sid: the docs stay open only as long as
    # the dashboard session that asked for them
    payload = {
        "scope": scope,
        "iss": _DOCS_TOKEN_ISSUER,
        "exp": int(time.time()) + ttl,
        "jti": secrets.token_urlsafe(16),
        "sid": session_id,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def docs_token_session(token: str, scope: DocsTokenScope, secret: str) -> Optional[int]:
    """The dashboard session a valid docs token of this scope belongs to."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"], issuer=_DOCS_TOKEN_ISSUER)
    except jwt.PyJWTError:
        return None
    session_id = payload.get("sid")
    if payload.get("scope") != scope or not isinstance(session_id, int):
        return None
    return session_id
