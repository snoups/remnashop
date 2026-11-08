from datetime import datetime
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict

SERVER_OWNED_FIELDS: Final[frozenset[str]] = frozenset({"id", "created_at", "updated_at"})


class BaseDto(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore")

    # 0 = not persisted yet (excluded via SERVER_OWNED_FIELDS); serial PKs never
    # assign 0, so no Optional. Don't truth-test `id`.
    id: int = 0


class TimestampMixin(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore")

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
