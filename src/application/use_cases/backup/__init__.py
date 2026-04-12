from typing import Final

from src.application.common import Interactor

from .commands import AutoBackupDatabase, BackupAssets, BackupDatabase, CreateAssetsDump, CreateDatabaseDump

BACKUP_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    AutoBackupDatabase,
    BackupAssets,
    BackupDatabase,
    CreateAssetsDump,
    CreateDatabaseDump,
)
