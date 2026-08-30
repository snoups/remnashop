from datetime import datetime
from typing import Any, Final

from sqlalchemy import DateTime, Function, func
from sqlalchemy.orm import Mapped, mapped_column

NOW_FUNC: Final[Function[Any]] = func.timezone("UTC", func.now())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=NOW_FUNC,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=NOW_FUNC,
        onupdate=NOW_FUNC,
        nullable=False,
    )
