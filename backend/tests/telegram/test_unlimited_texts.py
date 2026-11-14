from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

from app.modules.dialogs import catalog, register_all_flow_metadata
from app.modules.dialogs.catalog import get_condition
from app.telegram.i18n import format_expiry, format_period
from tests.modules.subscriptions.factories import make_subscription_dto


def _runner() -> MagicMock:
    def get(key: str, **kwargs: Any) -> str:
        return f"{key}{kwargs}" if kwargs else key

    return MagicMock(get=get)


def test_format_period_zero_is_unlimited() -> None:
    assert format_period(_runner(), 0) == "time-unit.unlimited"


def test_format_expiry_unlimited_and_dated() -> None:
    assert (
        format_expiry(_runner(), datetime(2099, 5, 1, tzinfo=timezone.utc)) == "time-unit.no-expiry"
    )
    assert (
        format_expiry(_runner(), datetime(2027, 5, 1, 13, 5, tzinfo=timezone.utc)) == "01.05.2027"
    )
    assert (
        format_expiry(_runner(), datetime(2027, 5, 1, 13, 5, tzinfo=timezone.utc), with_time=True)
        == "01.05.2027 13:05"
    )


def test_renew_button_hidden_for_an_unlimited_subscription() -> None:
    catalog._reset_for_tests()
    register_all_flow_metadata()
    renewable = get_condition("renewable_subscription")
    forever = make_subscription_dto(expire_at=datetime(2099, 1, 1, tzinfo=timezone.utc))
    month = make_subscription_dto(expire_at=datetime(2027, 1, 1, tzinfo=timezone.utc))

    assert not renewable({"subscription": forever})
    assert renewable({"subscription": month})
    assert not renewable({"subscription": None})
    catalog._reset_for_tests()
