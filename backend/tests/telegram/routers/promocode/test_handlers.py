from pathlib import Path

from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.telegram.routers.promocode.handlers import _NOTIFICATION_BY_CODE, _refusal_key

_LOCALES_DIR = Path(__file__).parents[4] / "assets" / "translations"


def test_refusal_names_the_specific_reason() -> None:
    expired = ValidationError("expired", code=ErrorCode.PROMOCODE_EXPIRED)
    limit = ValidationError("limit", code=ErrorCode.PROMOCODE_LIMIT_REACHED)
    missing = NotFoundError("missing", code=ErrorCode.PROMOCODE_NOT_FOUND)

    assert _refusal_key(expired) == "ntf-promocode.expired"
    assert _refusal_key(missing) == "ntf-promocode.not-found"
    assert _refusal_key(limit) == "ntf-promocode.not-available"


def test_every_refusal_key_exists_in_each_locale() -> None:
    attributes = {key.split(".", 1)[1] for key in _NOTIFICATION_BY_CODE.values()}
    for menu in _LOCALES_DIR.glob("*/menu.ftl"):
        text = menu.read_text()
        assert all(f"    .{attribute} =" in text for attribute in attributes), menu
