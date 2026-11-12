from datetime import timedelta

import pytest

import app.telegram.i18n as i18n
from app.core.enums import Locale
from app.core.utils.time import datetime_now
from app.telegram.i18n import build_translator_hub, format_wait
from tests.seeded_translations import seeded_fluent_source


@pytest.mark.parametrize(
    ("left", "expected"),
    [
        (timedelta(seconds=10), "1 мин"),
        (timedelta(minutes=45), "45 мин"),
        (timedelta(hours=2, minutes=14, seconds=30), "2 ч 15 мин"),
        (timedelta(hours=3), "3 ч"),
        (timedelta(days=1, hours=3, minutes=40), "1 день 3 ч"),
        (timedelta(days=5), "5 дней"),
        (timedelta(seconds=-5), "1 мин"),
    ],
)
def test_wait_is_days_and_hours_or_hours_and_minutes(
    monkeypatch: pytest.MonkeyPatch, left: timedelta, expected: str
) -> None:
    now = datetime_now()
    monkeypatch.setattr(i18n, "datetime_now", lambda: now)
    hub = build_translator_hub([Locale.RU], {Locale.RU: seeded_fluent_source(Locale.RU)}, Locale.RU)

    assert format_wait(hub.get_translator_by_locale("ru"), now + left) == expected
