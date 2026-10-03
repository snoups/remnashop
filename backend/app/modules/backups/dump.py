import asyncio
import os
import tempfile
import zipfile
from pathlib import Path

from app.core.config import AppConfig


async def create_database_dump(config: AppConfig, dest: Path) -> None:
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
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {stderr.decode()}")


def _build_assets_zip(media_dir: Path, final_path: Path) -> None:
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
                    file_path = root_path / name
                    zf.write(file_path, file_path.relative_to(prefix_root))
        os.replace(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)


async def create_assets_dump(config: AppConfig, dest_without_ext: Path) -> Path:
    final_path = dest_without_ext.with_suffix(".zip")
    await asyncio.to_thread(_build_assets_zip, config.media_dir, final_path)
    return final_path


async def restore_database_dump(config: AppConfig, dump_path: Path) -> None:
    db = config.database
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
        env={**os.environ, "PGPASSWORD": db.password.get_secret_value()},
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
