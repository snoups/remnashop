import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import AppConfig
from app.modules.backups import RestoreNotStartedError, restore_database_dump


def _process(returncode: int) -> AsyncMock:
    return AsyncMock(wait=AsyncMock(return_value=returncode))


async def test_restore_clears_the_schemas_before_pg_restore(tmp_path: Path) -> None:
    dump = tmp_path / "DATABASE_x.dump"
    with patch.object(
        asyncio, "create_subprocess_exec", AsyncMock(side_effect=[_process(0), _process(0)])
    ) as run:
        await restore_database_dump(AppConfig.get(), dump)

    clear, restore = (call.args for call in run.call_args_list)
    assert clear[0] == "psql"
    assert "DROP SCHEMA IF EXISTS public CASCADE" in clear[-1]
    assert "DROP SCHEMA IF EXISTS legacy CASCADE" in clear[-1]
    assert restore[0] == "pg_restore" and restore[-1] == str(dump)


async def test_restore_stops_when_clearing_fails(tmp_path: Path) -> None:
    with patch.object(
        asyncio, "create_subprocess_exec", AsyncMock(side_effect=[_process(1)])
    ) as run:
        with pytest.raises(RestoreNotStartedError):
            await restore_database_dump(AppConfig.get(), tmp_path / "DATABASE_x.dump")

    assert run.await_count == 1
