from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.timestamp import TimestampMixin
from app.core.enums import BackupKind, BackupRunStatus


class BackupRun(BaseSql, TimestampMixin):
    __tablename__ = "backup_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[BackupKind] = mapped_column(index=True)
    status: Mapped[BackupRunStatus] = mapped_column(index=True)

    file_path: Mapped[Optional[str]] = mapped_column(String(1024))
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger())
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64))

    triggered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    error: Mapped[Optional[str]]
    finished_at: Mapped[Optional[datetime]]
