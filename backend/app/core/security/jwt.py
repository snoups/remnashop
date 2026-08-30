import time
from typing import TypedDict, cast

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
