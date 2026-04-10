from dataclasses import dataclass
from typing import Union

from src.core.enums import Role

from .key_builder import StorageKey

SETTINGS_PREFIX = "settings"

USER_LIST_PREFIX = "user_list"
USER_COUNT_PREFIX = "user_count"

# TODO: Add version field?


@dataclass(frozen=True)
class UserCacheKey(StorageKey, prefix="user"):
    telegram_id: int


@dataclass(frozen=True)
class RoleKey(StorageKey, prefix="user_list"):
    role: Union[Role, tuple[Role, ...]]


@dataclass(frozen=True)
class WebhookLockKey(StorageKey, prefix="webhook_lock"):
    bot_id: int
    webhook_hash: str


@dataclass(frozen=True)
class LatestNotifiedVersionKey(StorageKey, prefix="latest_notified_version"):
    version: str


@dataclass(frozen=True)
class WelcomedVersionKey(StorageKey, prefix="welcomed_version"):
    version: str


class PaymentWaitlistKey(StorageKey, prefix="payment_waitlist"): ...


class ImportRunningKey(StorageKey, prefix="import_running"): ...


class SyncRunningKey(StorageKey, prefix="sync_running"): ...
