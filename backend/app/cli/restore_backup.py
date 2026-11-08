from pathlib import Path
from typing import Callable, Final, Optional

from app.cli.audit import record_rescue
from app.cli.legacy.schema import LEGACY_REVISIONS, current_revision
from app.core.config import AppConfig
from app.core.constants import BACKUP_DIR
from app.core.db.standalone import standalone_session
from app.modules.backups import (
    ProvenanceResult,
    ProvenanceStatus,
    RestoreNotStartedError,
    restore_database_dump,
    terminate_other_backends,
    verify_backup_file,
)

_MESSAGE_BY_STATUS: Final[dict[ProvenanceStatus, str]] = {
    ProvenanceStatus.NATIVE: "native -- produced by this deployment",
    ProvenanceStatus.UNSTAMPED: "unstamped -- no provenance trailer found, NOT verified",
    ProvenanceStatus.FOREIGN: "foreign -- signed by a different deployment, NOT verified",
    ProvenanceStatus.MALFORMED: "malformed -- trailer present but corrupt, NOT verified",
}
_RESTART: Final[str] = "Restart api/telegram/worker on this host now."
# the old schema has no audit log, and the new api would migrate it again on start
_LEGACY_RESTORED: Final[str] = (
    "This is an old-version database (revision {revision}), not recorded in the audit log. "
    "To go back to the old version: stop the new stack (`docker compose down`) and start the "
    "old image. To migrate it again: start the new stack, its api migrates the database on start."
)


def list_database_backups(backup_dir: Path = BACKUP_DIR) -> list[Path]:
    if not backup_dir.exists():
        return []
    return sorted(backup_dir.glob("DATABASE_*.dump"), reverse=True)


def format_provenance_message(result: ProvenanceResult) -> str:
    return _MESSAGE_BY_STATUS[result.status]


async def run_restore(
    path: Path,
    *,
    config: AppConfig,
    confirm_foreign: Callable[[], bool],
    confirm_start: Callable[[], bool],
) -> None:
    result = verify_backup_file(path, config.crypt_key.get_secret_value())
    print(f"Provenance: {format_provenance_message(result)}")

    if result.status is not ProvenanceStatus.NATIVE and not confirm_foreign():
        print("Aborted: archive not verified and operator did not confirm.")
        return

    print(
        "STOP the api, telegram and worker processes on this host BEFORE continuing "
        "-- a live process writing during the restore corrupts it."
    )
    if not confirm_start():
        print("Aborted.")
        return

    terminated = await terminate_other_backends(config)
    print(f"Terminated {terminated} competing database session(s).")

    print("Restoring... (this can take a while)")
    try:
        await restore_database_dump(config, path)
    except RestoreNotStartedError as error:
        print(f"{error} -- check the psql output above. The database was left as it was.")
        return
    except RuntimeError:
        advice = await _finish_restore(config)
        print(f"Restore finished with errors -- check the pg_restore output above. {advice}")
        return
    advice = await _finish_restore(config)
    print(f"Restore complete. {advice}")


async def _finish_restore(config: AppConfig) -> str:
    """Records the restore where the schema has an audit log; returns the next step."""
    revision = await _restored_revision(config)
    if revision in LEGACY_REVISIONS:
        return _LEGACY_RESTORED.format(revision=revision)
    await _record_restore(config)
    return _RESTART


async def _restored_revision(config: AppConfig) -> Optional[str]:
    async with standalone_session(config) as session:
        return await current_revision(await session.connection())


async def _record_restore(config: AppConfig) -> None:
    # into the restored database, after the dump replaced the audit log too
    try:
        async with standalone_session(config) as session:
            await record_rescue(session, "restore_backup")
            await session.commit()
    except Exception as error:
        print(f"Could not record the restore in the audit log: {error}")
