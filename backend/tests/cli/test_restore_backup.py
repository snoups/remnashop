from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.cli.restore_backup import format_provenance_message, list_database_backups, run_restore
from app.core.config import AppConfig
from app.modules.backups.provenance import ProvenanceResult, ProvenanceStatus


def test_list_database_backups_orders_newest_first(tmp_path: Path) -> None:
    older = tmp_path / "DATABASE_2026-01-01_00-00-00.dump"
    newer = tmp_path / "DATABASE_2026-01-02_00-00-00.dump"
    older.write_bytes(b"x")
    newer.write_bytes(b"x")
    (tmp_path / "ASSETS_2026-01-01_00-00-00.zip").write_bytes(b"x")

    result = list_database_backups(tmp_path)
    assert result == [newer, older]


def test_list_database_backups_missing_dir_returns_empty(tmp_path: Path) -> None:
    assert list_database_backups(tmp_path / "nope") == []


def test_format_provenance_message_for_each_status() -> None:
    for status in ProvenanceStatus:
        message = format_provenance_message(ProvenanceResult(status=status))
        assert isinstance(message, str) and message


async def test_run_restore_aborts_on_foreign_archive_without_confirmation(tmp_path: Path) -> None:
    path = tmp_path / "DATABASE_x.dump"
    path.write_bytes(b"not signed by us")

    with (
        patch("app.cli.restore_backup.restore_database_dump", AsyncMock()) as restore_mock,
        patch("app.cli.restore_backup.terminate_other_backends", AsyncMock(return_value=0)),
    ):
        await run_restore(
            path,
            config=AppConfig.get(),
            confirm_foreign=lambda: False,
            confirm_start=lambda: True,
        )

    restore_mock.assert_not_called()


async def test_run_restore_aborts_when_start_declined(tmp_path: Path) -> None:
    path = tmp_path / "DATABASE_x.dump"
    path.write_bytes(b"not signed by us")

    with (
        patch("app.cli.restore_backup.restore_database_dump", AsyncMock()) as restore_mock,
        patch(
            "app.cli.restore_backup.terminate_other_backends", AsyncMock(return_value=0)
        ) as terminate_mock,
    ):
        await run_restore(
            path,
            config=AppConfig.get(),
            confirm_foreign=lambda: True,
            confirm_start=lambda: False,
        )

    terminate_mock.assert_not_called()
    restore_mock.assert_not_called()


async def test_run_restore_runs_when_confirmed(tmp_path: Path) -> None:
    path = tmp_path / "DATABASE_x.dump"
    path.write_bytes(b"not signed by us")

    with (
        patch("app.cli.restore_backup.restore_database_dump", AsyncMock()) as restore_mock,
        patch(
            "app.cli.restore_backup.terminate_other_backends", AsyncMock(return_value=3)
        ) as terminate_mock,
    ):
        await run_restore(
            path,
            config=AppConfig.get(),
            confirm_foreign=lambda: True,
            confirm_start=lambda: True,
        )

    terminate_mock.assert_awaited_once()
    restore_mock.assert_awaited_once_with(AppConfig.get(), path)
