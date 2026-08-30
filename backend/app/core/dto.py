from datetime import datetime
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict

SERVER_OWNED_FIELDS: Final[set[str]] = {"id", "created_at", "updated_at"}


class BaseDto(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore")

    # 0 means "not persisted yet" (a DTO built for repository.create(),
    # excluded via SERVER_OWNED_FIELDS). Not Optional[int]: every DTO that
    # round-tripped through the DB always has a real id, and Postgres serial
    # PKs never assign 0, so this stays a safe sentinel rather than a
    # collidable one -- just don't treat `id` as falsy-checkable.
    id: int = 0


class TimestampMixin(BaseModel):
    model_config = ConfigDict(strict=False, extra="ignore")

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
