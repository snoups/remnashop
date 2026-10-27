import pytest
from sqlalchemy import text

from app.core.config import AppConfig
from app.core.config.database import DatabaseConfig
from app.core.db.standalone import standalone_session


def test_timeout_defaults_match_current_hardcoded_values() -> None:
    config = DatabaseConfig(password="test")
    assert config.statement_timeout_ms == 60_000
    assert config.idle_in_transaction_timeout_ms == 300_000
    assert config.command_timeout_s == 75
    assert config.connect_timeout_s == 10


def test_timeouts_are_overridable_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_PASSWORD", "test")
    monkeypatch.setenv("DATABASE_STATEMENT_TIMEOUT_MS", "120000")
    config = DatabaseConfig()
    assert config.statement_timeout_ms == 120_000


def test_postgres_times_a_statement_out_before_the_driver_does() -> None:
    config = DatabaseConfig(password="test")
    assert config.command_timeout_s * 1000 > config.statement_timeout_ms


def test_every_session_runs_in_utc() -> None:
    from app.core.db.standalone import connect_args  # noqa: PLC0415

    assert connect_args(DatabaseConfig(password="test"))["server_settings"]["timezone"] == "UTC"


async def test_a_session_gives_up_waiting_for_a_lock(config: AppConfig) -> None:
    async with standalone_session(config) as session:
        timeout = await session.scalar(text("SHOW lock_timeout"))
    assert timeout == f"{config.database.lock_timeout_ms // 1000}s"
