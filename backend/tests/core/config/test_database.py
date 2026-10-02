import pytest

from app.core.config.database import DatabaseConfig


def test_timeout_defaults_match_current_hardcoded_values() -> None:
    config = DatabaseConfig(password="test")
    assert config.statement_timeout_ms == 60_000
    assert config.idle_in_transaction_timeout_ms == 300_000
    assert config.command_timeout_s == 30
    assert config.connect_timeout_s == 10


def test_timeouts_are_overridable_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_PASSWORD", "test")
    monkeypatch.setenv("DATABASE_STATEMENT_TIMEOUT_MS", "120000")
    config = DatabaseConfig()
    assert config.statement_timeout_ms == 120_000
