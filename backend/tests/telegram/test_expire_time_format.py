from datetime import timedelta

from app.core.utils.time import datetime_now
from app.telegram.i18n import i18n_format_expire_time


def test_format_expire_time_future() -> None:
    expiry = datetime_now() + timedelta(days=5, hours=3)
    result = i18n_format_expire_time(expiry)
    assert result == expiry.strftime("%d.%m.%Y %H:%M")


def test_format_expire_time_none() -> None:
    assert i18n_format_expire_time(None) == "—"
