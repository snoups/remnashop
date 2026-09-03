import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.backups.repository import BackupRepository


@pytest.fixture
def backup_repository(session: AsyncSession) -> BackupRepository:
    return BackupRepository(session)
