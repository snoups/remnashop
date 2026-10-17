from pathlib import Path
from typing import Callable, Final

from app.core.config import AppConfig
from app.core.constants import BACKUP_DIR
from app.modules.backups import (
    ProvenanceResult,
    ProvenanceStatus,
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
    except RuntimeError:
        print(
            "Restore finished with errors -- check the pg_restore output above. "
            "Restart api/telegram/worker on this host."
        )
        return
    print("Restore complete. Restart api/telegram/worker on this host now.")
