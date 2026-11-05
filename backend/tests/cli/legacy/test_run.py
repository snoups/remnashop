import os
from pathlib import Path
from typing import Awaitable, Callable, Optional

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.cli.legacy import run as run_module
from app.cli.legacy.errors import LegacyMigrationError
from app.cli.legacy.migrate import MigrationResult, OwnerCredentials, migrate
from app.cli.legacy.panel import PanelIndex
from app.cli.legacy.report import MigrationReport
from app.cli.legacy.run import (
    backup_revision,
    deliver_report,
    read_bot_owner_id,
    render_report,
    rollback_advice,
    run_migration,
)
from app.cli.legacy.schema import LEGACY_HEAD, current_revision
from app.core.config import AppConfig

LegacyAt = Callable[[AsyncEngine, str], Awaitable[None]]
_PASSWORD = "s3cret-pass-word"


def _result(owner: bool = True) -> MigrationResult:
    return MigrationResult(
        report=MigrationReport(),
        owner=OwnerCredentials(login="boss", password=_PASSWORD) if owner else None,
        original_revision="0039",
    )


def test_render_report_password_only_when_asked(tmp_path: Path) -> None:
    backup = tmp_path / "b.dump"
    assert _PASSWORD not in render_report(_result(), backup, with_password=False)
    assert _PASSWORD in render_report(_result(), backup, with_password=True)
    assert "boss" in render_report(_result(), backup, with_password=False)


def test_deliver_report_file_has_no_password(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    backup = tmp_path / "b.dump"
    deliver_report(_result(), backup)
    assert _PASSWORD not in (tmp_path / "b.report.txt").read_text()
    assert _PASSWORD in capsys.readouterr().out


def test_rollback_advice_by_original_revision(tmp_path: Path) -> None:
    assert "No pre-migration backup" in rollback_advice(tmp_path)

    old = tmp_path / "DATABASE_pre-legacy-migration_0039_2026.dump"
    old.touch()
    assert backup_revision(old) == "0039"
    assert "Restore backup" in rollback_advice(tmp_path)

    head = tmp_path / f"DATABASE_pre-legacy-migration_{LEGACY_HEAD}_2027.dump"
    head.touch()
    os.utime(head, (old.stat().st_mtime + 10,) * 2)
    assert "start the old image" in rollback_advice(tmp_path)
    assert "Restore backup" not in rollback_advice(tmp_path)


@pytest.mark.parametrize(
    ("raw", "expected"), [("123", 123), ("abc", None), ("", None), (None, None)]
)
def test_read_bot_owner_id(
    monkeypatch: pytest.MonkeyPatch, raw: Optional[str], expected: Optional[int]
) -> None:
    if raw is None:
        monkeypatch.delenv("BOT_OWNER_ID", raising=False)
    else:
        monkeypatch.setenv("BOT_OWNER_ID", raw)
    assert read_bot_owner_id() == expected


async def test_run_migration_refuses_current_database(
    legacy_engine: AsyncEngine,
    config: AppConfig,
    legacy_at: LegacyAt,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await legacy_at(legacy_engine, LEGACY_HEAD)
    await migrate(
        legacy_engine,
        panel_index=PanelIndex(),
        crypt_key=config.crypt_key.get_secret_value(),
        bot_owner_id=None,
        original_revision=LEGACY_HEAD,
    )
    pointed = config.model_copy(
        update={"database": config.database.model_copy(update={"name": legacy_engine.url.database})}
    )
    monkeypatch.setattr(run_module, "BACKUP_DIR", Path("/nonexistent-no-backup"))

    with pytest.raises(LegacyMigrationError, match="Nothing to migrate"):
        await run_migration(pointed)

    async with legacy_engine.connect() as connection:
        assert await current_revision(connection) == "current"
        assert await connection.scalar(text("SELECT count(*) FROM legacy.users")) == 0
