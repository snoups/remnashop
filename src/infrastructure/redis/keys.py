from dataclasses import dataclass

from .key_builder import StorageKey

SETTINGS_PREFIX = "settings"

USER_LIST_PREFIX = "user_list"
USER_COUNT_PREFIX = "user_count"

# TODO: Add version field?


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


class RecentActivityKey(StorageKey, prefix="recent_activity"): ...


class ImportRunningKey(StorageKey, prefix="import_running"): ...


class SyncPanelRunningKey(StorageKey, prefix="sync_panel_running"): ...


class SyncBotRunningKey(StorageKey, prefix="sync_bot_running"): ...


@dataclass(frozen=True)
class RefreshTokenKey(StorageKey, prefix="refresh"):
    token: str


@dataclass(frozen=True)
class UserTokensKey(StorageKey, prefix="user_tokens"):
    user_id: int
