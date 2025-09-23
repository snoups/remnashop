from src.core.utils.key_builder import StorageKey


class WebhookLockKey(StorageKey, prefix="webhook_lock"):
    bot_id: int
    webhook_hash: str


class MaintenanceModeKey(StorageKey, prefix="maintenance_mode"): ...


class MaintenanceWaitListKey(StorageKey, prefix="maintenance_wait_list"): ...


class DefaultCurrencyKey(StorageKey, prefix="default_currency"): ...


class SystemNotificationSettingsKey(StorageKey, prefix="system_notification_settings"): ...


class UserNotificationSettingsKey(StorageKey, prefix="user_notification_settings"): ...


class RecentRegisteredUsersKey(StorageKey, prefix="recent_registered_users"): ...


class RecentActivityUsersKey(StorageKey, prefix="recent_activity_users"): ...
