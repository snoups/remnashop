from datetime import timedelta

from app.core.utils.i18n_helpers import (
    i18n_format_device_limit,
    i18n_format_expire_time,
    i18n_format_traffic_limit,
)
from app.core.utils.time import datetime_now


def test_format_expire_time_future() -> None:
    expiry = datetime_now() + timedelta(days=5, hours=3)
    result = i18n_format_expire_time(expiry)
    assert result == expiry.strftime("%d.%m.%Y %H:%M")


def test_format_expire_time_none() -> None:
    assert i18n_format_expire_time(None) == "—"


def test_format_traffic_limit_finite() -> None:
    assert i18n_format_traffic_limit(100) == "100 GB"


def test_format_traffic_limit_unlimited() -> None:
    assert i18n_format_traffic_limit(0) == "Unlimited"


def test_format_device_limit_finite() -> None:
    assert i18n_format_device_limit(3) == "3 devices"


def test_format_device_limit_unlimited() -> None:
    assert i18n_format_device_limit(0) == "Unlimited"
