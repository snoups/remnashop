import asyncio
import os
import shutil
from pathlib import Path

from src.application.common import Interactor
from src.application.dto import UserDto
from src.core.config import AppConfig


class CreateDatabaseDump(Interactor[Path, None]):
    required_permission = None

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def _execute(self, actor: UserDto, dump_file: Path) -> None:
        db = self.config.database
        proc = await asyncio.create_subprocess_exec(
            "pg_dump",
            "-h",
            db.host,
            "-p",
            str(db.port),
            "-U",
            db.user,
            "-d",
            db.name,
            "-f",
            str(dump_file),
            env={**os.environ, "PGPASSWORD": db.password.get_secret_value()},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {stderr.decode()}")


class CreateAssetsDump(Interactor[Path, None]):
    required_permission = None

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def _execute(self, actor: UserDto, zip_path: Path) -> None:
        await asyncio.to_thread(
            shutil.make_archive,
            str(zip_path),
            "zip",
            str(self.config.assets_dir.parent),
            str(self.config.assets_dir.name),
        )
