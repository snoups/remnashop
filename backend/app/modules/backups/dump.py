import asyncio
import os
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Final

from app.core.config import AppConfig
from app.modules.backups.provenance import sign_backup_file

BACKUP_FILE_MODE: Final[int] = 0o600
# a dump recreates only its own objects: a table added since, referencing one of
# them, would block its drop and leave two schemas mixed. `legacy` holds the old
# version's data after a migration; a dump that has it brings it back.
_CLEAR_SCHEMAS: Final[str] = (
    "SET client_min_messages = warning; "
    "DROP SCHEMA IF EXISTS legacy CASCADE; DROP SCHEMA IF EXISTS public CASCADE; "
    "CREATE SCHEMA public;"
)


class RestoreNotStartedError(RuntimeError):
    """Clearing the database failed: nothing was dropped or restored."""


async def create_database_dump(config: AppConfig, dest: Path) -> None:
    # created owner-only up front: pg_dump keeps the mode, so the file is never
    # readable by others while it is being written
    os.close(os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, BACKUP_FILE_MODE))
    os.chmod(dest, BACKUP_FILE_MODE)
    try:
        await _run_pg_dump(config, dest)
    except BaseException:
        # a half-written dump must not be offered for a restore
        dest.unlink(missing_ok=True)
        raise


async def _run_pg_dump(config: AppConfig, dest: Path) -> None:
    db = config.database
    proc = await asyncio.create_subprocess_exec(
        "pg_dump",
        "-Fc",
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.name,
        "-f",
        str(dest),
        env={**os.environ, "PGPASSWORD": db.password.get_secret_value()},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await proc.communicate()
    except asyncio.CancelledError:
        # canceling the wait leaves the process running on its own
        proc.terminate()
        await proc.wait()
        raise
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {stderr.decode()}")


async def create_signed_database_dump(config: AppConfig, dest: Path) -> None:
    await create_database_dump(config, dest)
    sign_backup_file(dest, config.crypt_key.get_secret_value())


def _build_assets_zip(media_dir: Path, final_path: Path, stop: threading.Event) -> None:
    backups_dir = media_dir / "backups"
    prefix_root = media_dir.parent
    # media/ is its own volume, and os.replace() (rename(2)) raises EXDEV
    # across devices, so the temp file lives in backups_dir; the walk below
    # skips that dir, so it never archives itself.
    backups_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=backups_dir, suffix=".zip")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(media_dir):
                root_path = Path(root)
                if root_path == backups_dir or backups_dir in root_path.parents:
                    dirs[:] = []
                    continue
                for name in files:
                    # a thread can't be canceled from outside: it checks between files
                    if stop.is_set():
                        return
                    file_path = root_path / name
                    zf.write(file_path, file_path.relative_to(prefix_root))
        os.replace(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)


async def create_assets_dump(config: AppConfig, dest_without_ext: Path) -> Path:
    final_path = dest_without_ext.with_suffix(".zip")
    stop = threading.Event()
    build = asyncio.ensure_future(
        asyncio.to_thread(_build_assets_zip, config.media_dir, final_path, stop)
    )
    try:
        await asyncio.shield(build)
    except asyncio.CancelledError:
        stop.set()
        await build
        raise
    return final_path


async def restore_database_dump(config: AppConfig, dump_path: Path) -> None:
    db = config.database
    env = {**os.environ, "PGPASSWORD": db.password.get_secret_value()}
    # one -c is one transaction: either the schemas are cleared or nothing is
    clear = await asyncio.create_subprocess_exec(
        "psql",
        "-q",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.name,
        "-c",
        _CLEAR_SCHEMAS,
        env=env,
    )
    if await clear.wait() != 0:
        raise RestoreNotStartedError("Clearing the database before the restore failed")
    proc = await asyncio.create_subprocess_exec(
        "pg_restore",
        "--clean",
        "--if-exists",
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.name,
        str(dump_path),
        env=env,
    )
    returncode = await proc.wait()
    if returncode != 0:
        raise RuntimeError(f"pg_restore exited with code {returncode}")


async def terminate_other_backends(config: AppConfig) -> int:
    db = config.database
    proc = await asyncio.create_subprocess_exec(
        "psql",
        "-h",
        db.host,
        "-p",
        str(db.port),
        "-U",
        db.user,
        "-d",
        db.name,
        "-t",
        "-c",
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = current_database() AND pid <> pg_backend_pid();",
        env={**os.environ, "PGPASSWORD": db.password.get_secret_value()},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return 0
    return stdout.decode().count("t")
