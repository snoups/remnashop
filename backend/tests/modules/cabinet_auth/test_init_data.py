import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.modules.cabinet_auth.init_data import codes_from_start_param, verify_init_data

_TOKEN = "123456:TEST-token"


def _sign(fields: dict[str, str], token: str = _TOKEN) -> str:
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields = {**fields, "hash": hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()}
    return urlencode(fields)


def _fields(auth_date: int = 1_000_000, **extra: str) -> dict[str, str]:
    user = json.dumps({"id": 42, "first_name": "Ann", "username": "ann", "language_code": "ru"})
    return {"auth_date": str(auth_date), "user": user, **extra}


def test_valid_init_data() -> None:
    data = verify_init_data(_sign(_fields(start_param="ref_abc")), _TOKEN, now=1_000_100)
    assert data.profile.telegram_id == 42 and data.profile.username == "ann"
    assert data.start_param == "ref_abc"


@pytest.mark.parametrize(
    "init_data",
    [
        _sign(_fields(), token="999:other"),  # чужой бот
        _sign(_fields()).replace("Ann", "Bob"),  # подмена поля
        _sign(_fields(auth_date=1_000_000 - 90_000)),  # старше суток
        "user=%7B%7D",  # нет hash
    ],
)
def test_invalid_init_data(init_data: str) -> None:
    with pytest.raises(AuthenticationError) as error:
        verify_init_data(init_data, _TOKEN, now=1_000_000)
    assert error.value.code is ErrorCode.INVALID_INIT_DATA


@pytest.mark.parametrize(
    "user",
    ["[1]", '"x"', "5", "null", '{"id": 1, "first_name": 5}', '{"id": 1, "username": ["a"]}'],
)
def test_signed_user_of_wrong_shape_is_invalid(user: str) -> None:
    init_data = _sign({"auth_date": "1000000", "user": user})
    with pytest.raises(AuthenticationError) as error:
        verify_init_data(init_data, _TOKEN, now=1_000_000)
    assert error.value.code is ErrorCode.INVALID_INIT_DATA


def test_codes_from_start_param() -> None:
    assert codes_from_start_param("ref_abc").referral_code == "abc"
    assert codes_from_start_param("ad_yt").ad_link_code == "yt"
    assert codes_from_start_param("webauth_x").referral_code is None
    assert codes_from_start_param(None).ad_link_code is None
