from src.core.storage.key_builder import StorageKey


class WebhookLockKey(StorageKey, prefix="webhook_lock"):
    bot_id: int
    webhook_hash: str


class LastNotifiedVersionKey(StorageKey, prefix="last_notified_version"): ...


class SyncRunningKey(StorageKey, prefix="sync_running"): ...


class AccessWaitListKey(StorageKey, prefix="access_wait_list"): ...


class RecentActivityUsersKey(StorageKey, prefix="recent_activity_users"): ...
