from datetime import timedelta
from typing import Optional

import pytest
from aiogram.types import WebhookInfo

from app.core.utils.time import datetime_now
from app.telegram.lifespan import is_fresh_webhook_error


def _info(message: Optional[str], minutes_ago: Optional[int]) -> WebhookInfo:
    date = None if minutes_ago is None else datetime_now() - timedelta(minutes=minutes_ago)
    return WebhookInfo(
        url="https://x",
        has_custom_certificate=False,
        pending_update_count=0,
        last_error_message=message,
        last_error_date=date,
    )


@pytest.mark.parametrize(
    ("message", "minutes_ago", "expected"),
    [
        ("Wrong response", 1, True),
        ("Wrong response", 120, False),
        ("Wrong response", None, False),
        (None, 1, False),
    ],
)
def test_only_a_recent_webhook_error_counts(
    message: Optional[str], minutes_ago: Optional[int], expected: bool
) -> None:
    assert is_fresh_webhook_error(_info(message, minutes_ago), datetime_now()) is expected
