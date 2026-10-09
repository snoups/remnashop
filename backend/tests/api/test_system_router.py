from datetime import datetime, timezone

from app.api.system_router import parse_commit_date


def test_commit_date_parses_iso_time() -> None:
    assert parse_commit_date("2026-10-09T12:00:00+00:00") == datetime(
        2026, 10, 9, 12, tzinfo=timezone.utc
    )


def test_malformed_commit_date_is_none() -> None:
    assert parse_commit_date("garbage") is None
    assert parse_commit_date(None) is None
