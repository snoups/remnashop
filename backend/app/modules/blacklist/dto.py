from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.core.enums import BlacklistKind


@dataclass(frozen=True, kw_only=True)
class BlacklistDto:
    telegram_ids: list[int] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BlacklistSourceDto:
    id: int
    url: str
    name: Optional[str]
    enabled: bool
    entries_count: int
    last_synced_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, kw_only=True)
class BlacklistEntryInputDto:
    kind: BlacklistKind
    value: str


@dataclass(frozen=True, kw_only=True)
class AddBlacklistSourceDto:
    url: str
    name: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class ToggleBlacklistSourceDto:
    source_id: int
    enabled: bool


@dataclass(frozen=True, kw_only=True)
class ParsedSourceList:
    telegram_ids: list[int] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class BlacklistOriginDto:
    # None = the manual list
    source_id: Optional[int] = None
    source_name: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class BlacklistOriginsDto:
    telegram_ids: dict[int, list[BlacklistOriginDto]] = field(default_factory=dict)
    emails: dict[str, list[BlacklistOriginDto]] = field(default_factory=dict)
