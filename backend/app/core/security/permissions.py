from __future__ import annotations

from dataclasses import dataclass
from enum import auto
from typing import Final, Literal

from app.core.actor import Actor
from app.core.enums import Role, UpperStrEnum
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError


class Permission(UpperStrEnum):
    PUBLIC = auto()
    ANALYTICS_VIEW = auto()
    ANALYTICS_FUNNEL_VIEW = auto()
    ANALYTICS_COHORTS_VIEW = auto()
    ANALYTICS_LTV_VIEW = auto()
    ANALYTICS_LTV_BREAKDOWN_VIEW = auto()
    ANALYTICS_REVENUE_VIEW = auto()
    ANALYTICS_TRIAL_VIEW = auto()
    ANALYTICS_RETENTION_VIEW = auto()
    ANALYTICS_SOURCES_VIEW = auto()
    ANALYTICS_PROMOCODES_VIEW = auto()
    REMNAWAVE_NODES_VIEW = auto()
    REMNAWAVE_CLIENT_APPS_VIEW = auto()
    BOT_SETTINGS_VIEW = auto()
    BOT_STATUS_VIEW = auto()
    BOT_LOGS_VIEW = auto()
    BOT_COMMANDS_VIEW = auto()
    BOT_SETTINGS_MANAGE = auto()
    BOT_COMMANDS_MANAGE = auto()
    BOT_REQUIREMENTS_VIEW = auto()
    BOT_REQUIREMENTS_MANAGE = auto()
    BOT_RESTART = auto()
    BOT_PROXY_SET = auto()
    BOT_PROXY_REMOVE = auto()
    SHOP_SETTINGS_VIEW = auto()
    SHOP_SETTINGS_MANAGE = auto()
    ACCESS_SETTINGS_VIEW = auto()
    ACCESS_SETTINGS_MANAGE = auto()
    PAYMENT_WAITLIST_VIEW = auto()
    OAUTH_SETTINGS_VIEW = auto()
    OAUTH_SETTINGS_MANAGE = auto()
    EMAIL_SETTINGS_VIEW = auto()
    EMAIL_SETTINGS_MANAGE = auto()
    EMAIL_SETTINGS_TEST = auto()
    EMAIL_SETTINGS_BULK_RESET = auto()
    CABINET_AUTH_SETTINGS_VIEW = auto()
    CABINET_AUTH_SETTINGS_MANAGE = auto()
    BANNERS_IMAGE_VIEW = auto()
    BANNERS_UPLOAD = auto()
    BANNERS_DELETE = auto()
    BANNERS_RESTORE_DEFAULT = auto()
    LEGAL_DOCUMENTS_VIEW = auto()
    LEGAL_DOCUMENTS_UPDATE = auto()
    LEGAL_TEXT_SET = auto()
    LEGAL_TEXT_REMOVE = auto()
    LEGAL_ACCEPTANCES_VIEW = auto()
    EMOJI_PACKS_VIEW = auto()
    EMOJI_PACKS_IMPORT = auto()
    EMOJI_PACKS_DELETE = auto()
    LOCALES_VIEW = auto()
    LOCALES_ADD = auto()
    LOCALES_REMOVE = auto()
    LOCALES_DEFAULT_SET = auto()
    TRANSLATIONS_VIEW = auto()
    TRANSLATIONS_UPDATE = auto()
    TRANSLATIONS_RESET = auto()
    TRANSLATIONS_RESET_ALL = auto()
    TRANSLATIONS_EXPORT = auto()
    TRANSLATIONS_IMPORT = auto()
    DIALOGS_WINDOWS_VIEW = auto()
    DIALOGS_CATALOG_VIEW = auto()
    DIALOGS_WINDOWS_UPDATE = auto()
    DIALOGS_WINDOWS_BUTTONS_UPDATE = auto()
    DIALOGS_WINDOWS_CREATE = auto()
    DIALOGS_WINDOWS_DELETE = auto()
    DIALOGS_WINDOWS_RESET = auto()
    DIALOGS_WINDOWS_RESET_ALL = auto()
    DIALOGS_TEXT_UPDATE = auto()
    DIALOGS_EXPORT = auto()
    DIALOGS_IMPORT = auto()
    OWN_ACCOUNT_MANAGE = auto()
    ADMINS_MANAGE = auto()
    API_TOKENS_MANAGE = auto()
    EVENT_LOG_VIEW = auto()
    EVENT_LOG_DETAIL_VIEW = auto()
    NOTIFICATIONS_VIEW = auto()
    NOTIFICATION_SETTINGS_VIEW = auto()
    NOTIFICATION_SETTINGS_MANAGE = auto()
    NOTIFICATION_VAPID_KEYS_GENERATE = auto()
    USERS_VIEW = auto()
    USERS_DETAIL_VIEW = auto()
    USERS_REGISTRATION_VIEW = auto()
    USERS_STATS_VIEW = auto()
    USERS_DELETE = auto()
    USERS_DISCOUNT_MANAGE = auto()
    USERS_LOYALTY_VIEW = auto()
    USERS_LOYALTY_MANAGE = auto()
    USER_SESSIONS_VIEW = auto()
    USER_SESSIONS_REVOKE = auto()
    APPEARANCE_SETTINGS_MANAGE = auto()
    APPEARANCE_SETTINGS_RESET = auto()
    APPEARANCE_LOGO_UPLOAD = auto()
    APPEARANCE_LOGO_DELETE = auto()
    APPEARANCE_FAVICON_UPLOAD = auto()
    APPEARANCE_FAVICON_DELETE = auto()
    GATEWAYS_VIEW = auto()
    GATEWAYS_UPDATE = auto()
    GATEWAYS_ACTIVE_SET = auto()
    GATEWAYS_REORDER = auto()
    GATEWAYS_TEST = auto()
    GATEWAYS_TEST_VIEW = auto()
    PLANS_VIEW = auto()
    PLANS_DETAIL_VIEW = auto()
    PLANS_SHARE_VIEW = auto()
    PLANS_CREATE = auto()
    PLANS_UPDATE = auto()
    PLANS_DELETE = auto()
    PLANS_DURATIONS_MANAGE = auto()
    PLANS_PRICE_OVERRIDE_MANAGE = auto()
    PLANS_DURATION_BASE_PRICE_MANAGE = auto()
    PLANS_ACCESS_MANAGE = auto()
    PLANS_SQUADS_MANAGE = auto()
    PLANS_DISCOUNT_MANAGE = auto()
    PLANS_ORDER_MANAGE = auto()
    PRICING_VIEW = auto()
    PRICING_PREVIEW_VIEW = auto()
    PRICING_RATES_MANAGE = auto()
    PRICING_ANCHOR_MANAGE = auto()
    PRICING_SETTINGS_MANAGE = auto()
    PRICING_BASE_ADJUST_MANAGE = auto()
    SUBSCRIPTIONS_VIEW = auto()
    SUBSCRIPTIONS_DETAIL_VIEW = auto()
    SUBSCRIPTIONS_UPDATE = auto()
    SUBSCRIPTIONS_SQUADS_MANAGE = auto()
    SUBSCRIPTIONS_DELETE = auto()
    SUBSCRIPTIONS_GRANT = auto()
    SUBSCRIPTIONS_PLAN_CHANGE = auto()
    SUBSCRIPTIONS_STATUS_MANAGE = auto()
    SUBSCRIPTIONS_TRAFFIC_RESET = auto()
    SUBSCRIPTIONS_LINK_REISSUE = auto()
    SUBSCRIPTIONS_DEVICES_VIEW = auto()
    SUBSCRIPTIONS_DEVICES_DELETE = auto()
    SUBSCRIPTIONS_DEVICES_DELETE_ALL = auto()
    SUBSCRIPTIONS_PANEL_DIFF_VIEW = auto()
    SUBSCRIPTIONS_PULL_FROM_PANEL = auto()
    SUBSCRIPTIONS_PUSH_TO_PANEL = auto()
    SUBSCRIPTIONS_PANEL_SYNC_STATUS_VIEW = auto()
    SUBSCRIPTIONS_PANEL_SYNC_FROM = auto()
    SUBSCRIPTIONS_PANEL_SYNC_TO = auto()
    ADDONS_VIEW = auto()
    ADDONS_DETAIL_VIEW = auto()
    ADDONS_CREATE = auto()
    ADDONS_UPDATE = auto()
    ADDONS_DELETE = auto()
    ADDONS_PRICES_MANAGE = auto()
    ADDONS_PRICE_OVERRIDE_MANAGE = auto()
    PROMOCODES_VIEW = auto()
    PROMOCODES_DETAIL_VIEW = auto()
    PROMOCODES_CREATE = auto()
    PROMOCODES_UPDATE = auto()
    PROMOCODES_DELETE = auto()
    PROMOCODES_GENERATE_CODE = auto()
    PROMOCODES_ACTIVATIONS_VIEW = auto()
    PROMOCODES_SUMMARY_VIEW = auto()
    PROMOCODES_USERS_VIEW = auto()
    BROADCASTS_VIEW = auto()
    BROADCASTS_DETAIL_VIEW = auto()
    BROADCASTS_CREATE = auto()
    BROADCASTS_UPDATE = auto()
    BROADCASTS_DELETE = auto()
    BROADCASTS_SEND = auto()
    BROADCASTS_RECALL = auto()
    BROADCASTS_CANCEL = auto()
    BROADCASTS_RETRY = auto()
    BROADCASTS_TEST_SEND = auto()
    BROADCASTS_RECIPIENTS_VIEW = auto()
    BROADCASTS_MEDIA_SET = auto()
    BROADCASTS_MEDIA_DELETE = auto()
    BROADCASTS_AUDIENCE_PREVIEW = auto()
    BROADCASTS_SUMMARY_VIEW = auto()
    BROADCASTS_EMAIL_IMAGE_ADD = auto()
    BROADCASTS_EMAIL_IMAGE_VIEW = auto()
    BROADCASTS_EMAIL_PREVIEW = auto()
    BROADCASTS_EMAIL_TEST_SEND = auto()
    TRANSACTIONS_VIEW = auto()
    TRANSACTIONS_SUMMARY_VIEW = auto()
    TRANSACTIONS_DETAIL_VIEW = auto()
    TRANSACTIONS_GATEWAYS_VIEW = auto()
    TRANSACTIONS_FULFILL = auto()
    TRANSACTIONS_REFUND = auto()
    TRANSACTIONS_REFUND_PREVIEW = auto()
    REFERRALS_VIEW = auto()
    REFERRALS_INVITED_VIEW = auto()
    REFERRALS_REVENUE_VIEW = auto()
    REFERRALS_LIST = auto()
    REFERRALS_SUMMARY_VIEW = auto()
    REFERRALS_SETTINGS_VIEW = auto()
    REFERRALS_SETTINGS_MANAGE = auto()
    REFERRALS_SETTINGS_RESET = auto()
    REFERRALS_POINTS_MANAGE = auto()
    REFERRALS_BONUS_DAYS_MANAGE = auto()
    REFERRALS_CODE_RESET = auto()
    LOYALTY_SETTINGS_VIEW = auto()
    LOYALTY_SETTINGS_MANAGE = auto()
    LOYALTY_SETTINGS_RESET = auto()
    BACKUPS_VIEW = auto()
    BACKUPS_SETTINGS_VIEW = auto()
    BACKUPS_SETTINGS_MANAGE = auto()
    BACKUPS_SETTINGS_RESET = auto()
    BACKUPS_RUN_VIEW = auto()
    BACKUPS_RUN_CREATE = auto()
    BACKUPS_RUN_DOWNLOAD = auto()
    BACKUPS_RUN_DELETE = auto()
    BACKUPS_STATS_VIEW = auto()
    BLACKLIST_VIEW = auto()
    BLACKLIST_SOURCES_VIEW = auto()
    BLACKLIST_SOURCE_DETAIL_VIEW = auto()
    BLACKLIST_ENTRY_ADD = auto()
    BLACKLIST_ENTRY_REMOVE = auto()
    BLACKLIST_SOURCE_ADD = auto()
    BLACKLIST_SOURCE_REMOVE = auto()
    BLACKLIST_SOURCE_UPDATE = auto()
    BLACKLIST_SYNC = auto()
    BLACKLIST_MATCHES_VIEW = auto()
    USERS_BLOCK = auto()
    USERS_EMAIL_UNDELIVERABLE_CLEAR = auto()
    USERS_UNBLOCK = auto()
    USERS_UNBLOCK_BLACKLIST_MATCHES = auto()
    USERS_MERGE_PREVIEW = auto()
    USERS_MERGE = auto()
    USERS_TELEGRAM_BIND = auto()
    AD_LINKS_VIEW = auto()
    AD_LINKS_DETAIL_VIEW = auto()
    AD_LINKS_STATS_VIEW = auto()
    AD_LINKS_SUMMARY_VIEW = auto()
    AD_LINKS_USERS_VIEW = auto()
    AD_LINKS_USER_ATTRIBUTION_VIEW = auto()
    AD_LINKS_SHARE_VIEW = auto()
    AD_LINKS_CREATE = auto()
    AD_LINKS_GENERATE_CODE = auto()
    AD_LINKS_UPDATE = auto()
    AD_LINKS_DELETE = auto()


@dataclass(frozen=True, kw_only=True)
class PermissionMeta:
    resource: str
    kind: Literal["read", "write"]


PERMISSION_METADATA: Final[dict[Permission, PermissionMeta]] = {
    Permission.BOT_SETTINGS_VIEW: PermissionMeta(resource="bot_settings", kind="read"),
    Permission.BOT_STATUS_VIEW: PermissionMeta(resource="bot_settings", kind="read"),
    Permission.BOT_LOGS_VIEW: PermissionMeta(resource="bot_settings", kind="read"),
    Permission.BOT_COMMANDS_VIEW: PermissionMeta(resource="bot_settings", kind="read"),
    Permission.BOT_SETTINGS_MANAGE: PermissionMeta(resource="bot_settings", kind="write"),
    Permission.BOT_COMMANDS_MANAGE: PermissionMeta(resource="bot_settings", kind="write"),
    Permission.BOT_REQUIREMENTS_VIEW: PermissionMeta(resource="bot_settings", kind="read"),
    Permission.BOT_REQUIREMENTS_MANAGE: PermissionMeta(resource="bot_settings", kind="write"),
    Permission.BOT_RESTART: PermissionMeta(resource="bot_settings", kind="write"),
    Permission.BOT_PROXY_SET: PermissionMeta(resource="bot_settings", kind="write"),
    Permission.BOT_PROXY_REMOVE: PermissionMeta(resource="bot_settings", kind="write"),
    Permission.SHOP_SETTINGS_VIEW: PermissionMeta(resource="shop_settings", kind="read"),
    Permission.SHOP_SETTINGS_MANAGE: PermissionMeta(resource="shop_settings", kind="write"),
    Permission.ACCESS_SETTINGS_VIEW: PermissionMeta(resource="access_settings", kind="read"),
    Permission.ACCESS_SETTINGS_MANAGE: PermissionMeta(resource="access_settings", kind="write"),
    Permission.PAYMENT_WAITLIST_VIEW: PermissionMeta(resource="access_settings", kind="read"),
    Permission.OAUTH_SETTINGS_VIEW: PermissionMeta(resource="oauth_settings", kind="read"),
    Permission.OAUTH_SETTINGS_MANAGE: PermissionMeta(resource="oauth_settings", kind="write"),
    Permission.EMAIL_SETTINGS_VIEW: PermissionMeta(resource="email_settings", kind="read"),
    Permission.EMAIL_SETTINGS_MANAGE: PermissionMeta(resource="email_settings", kind="write"),
    Permission.EMAIL_SETTINGS_TEST: PermissionMeta(resource="email_settings", kind="write"),
    Permission.EMAIL_SETTINGS_BULK_RESET: PermissionMeta(resource="email_settings", kind="write"),
    Permission.CABINET_AUTH_SETTINGS_VIEW: PermissionMeta(
        resource="cabinet_auth_settings", kind="read"
    ),
    Permission.CABINET_AUTH_SETTINGS_MANAGE: PermissionMeta(
        resource="cabinet_auth_settings", kind="write"
    ),
    Permission.BANNERS_IMAGE_VIEW: PermissionMeta(resource="banners", kind="read"),
    Permission.BANNERS_UPLOAD: PermissionMeta(resource="banners", kind="write"),
    Permission.BANNERS_DELETE: PermissionMeta(resource="banners", kind="write"),
    Permission.BANNERS_RESTORE_DEFAULT: PermissionMeta(resource="banners", kind="write"),
    Permission.LEGAL_DOCUMENTS_VIEW: PermissionMeta(resource="legal_documents", kind="read"),
    Permission.LEGAL_DOCUMENTS_UPDATE: PermissionMeta(resource="legal_documents", kind="write"),
    Permission.LEGAL_TEXT_SET: PermissionMeta(resource="legal_documents", kind="write"),
    Permission.LEGAL_TEXT_REMOVE: PermissionMeta(resource="legal_documents", kind="write"),
    Permission.LEGAL_ACCEPTANCES_VIEW: PermissionMeta(resource="legal_acceptances", kind="read"),
    Permission.EMOJI_PACKS_VIEW: PermissionMeta(resource="emoji_packs", kind="read"),
    Permission.EMOJI_PACKS_IMPORT: PermissionMeta(resource="emoji_packs", kind="write"),
    Permission.EMOJI_PACKS_DELETE: PermissionMeta(resource="emoji_packs", kind="write"),
    Permission.LOCALES_VIEW: PermissionMeta(resource="locales", kind="read"),
    Permission.LOCALES_ADD: PermissionMeta(resource="locales", kind="write"),
    Permission.LOCALES_REMOVE: PermissionMeta(resource="locales", kind="write"),
    Permission.LOCALES_DEFAULT_SET: PermissionMeta(resource="locales", kind="write"),
    Permission.TRANSLATIONS_VIEW: PermissionMeta(resource="translations", kind="read"),
    Permission.TRANSLATIONS_UPDATE: PermissionMeta(resource="translations", kind="write"),
    Permission.TRANSLATIONS_RESET: PermissionMeta(resource="translations", kind="write"),
    Permission.TRANSLATIONS_RESET_ALL: PermissionMeta(resource="translations", kind="write"),
    Permission.TRANSLATIONS_EXPORT: PermissionMeta(resource="translations", kind="read"),
    Permission.TRANSLATIONS_IMPORT: PermissionMeta(resource="translations", kind="write"),
    Permission.DIALOGS_WINDOWS_VIEW: PermissionMeta(resource="dialogs", kind="read"),
    Permission.DIALOGS_CATALOG_VIEW: PermissionMeta(resource="dialogs", kind="read"),
    Permission.DIALOGS_WINDOWS_UPDATE: PermissionMeta(resource="dialogs", kind="write"),
    Permission.DIALOGS_WINDOWS_BUTTONS_UPDATE: PermissionMeta(resource="dialogs", kind="write"),
    Permission.DIALOGS_WINDOWS_CREATE: PermissionMeta(resource="dialogs", kind="write"),
    Permission.DIALOGS_WINDOWS_DELETE: PermissionMeta(resource="dialogs", kind="write"),
    Permission.DIALOGS_WINDOWS_RESET: PermissionMeta(resource="dialogs", kind="write"),
    Permission.DIALOGS_WINDOWS_RESET_ALL: PermissionMeta(resource="dialogs", kind="write"),
    Permission.DIALOGS_TEXT_UPDATE: PermissionMeta(resource="dialogs", kind="write"),
    Permission.DIALOGS_EXPORT: PermissionMeta(resource="dialogs", kind="read"),
    Permission.DIALOGS_IMPORT: PermissionMeta(resource="dialogs", kind="write"),
    Permission.EVENT_LOG_VIEW: PermissionMeta(resource="event_log", kind="read"),
    Permission.EVENT_LOG_DETAIL_VIEW: PermissionMeta(resource="event_log", kind="read"),
    Permission.NOTIFICATIONS_VIEW: PermissionMeta(resource="event_log", kind="read"),
    Permission.NOTIFICATION_SETTINGS_VIEW: PermissionMeta(
        resource="notification_settings", kind="read"
    ),
    Permission.NOTIFICATION_SETTINGS_MANAGE: PermissionMeta(
        resource="notification_settings", kind="write"
    ),
    Permission.USERS_VIEW: PermissionMeta(resource="users", kind="read"),
    Permission.USERS_DETAIL_VIEW: PermissionMeta(resource="users", kind="read"),
    Permission.USERS_REGISTRATION_VIEW: PermissionMeta(resource="users", kind="read"),
    Permission.USERS_STATS_VIEW: PermissionMeta(resource="users", kind="read"),
    Permission.USERS_DELETE: PermissionMeta(resource="users", kind="write"),
    Permission.USERS_DISCOUNT_MANAGE: PermissionMeta(resource="users", kind="write"),
    Permission.USERS_LOYALTY_VIEW: PermissionMeta(resource="users", kind="read"),
    Permission.USERS_LOYALTY_MANAGE: PermissionMeta(resource="users", kind="write"),
    Permission.USER_SESSIONS_VIEW: PermissionMeta(resource="user_sessions", kind="read"),
    Permission.USER_SESSIONS_REVOKE: PermissionMeta(resource="user_sessions", kind="write"),
    Permission.APPEARANCE_SETTINGS_MANAGE: PermissionMeta(resource="appearance", kind="write"),
    Permission.APPEARANCE_SETTINGS_RESET: PermissionMeta(resource="appearance", kind="write"),
    Permission.APPEARANCE_LOGO_UPLOAD: PermissionMeta(resource="appearance", kind="write"),
    Permission.APPEARANCE_LOGO_DELETE: PermissionMeta(resource="appearance", kind="write"),
    Permission.APPEARANCE_FAVICON_UPLOAD: PermissionMeta(resource="appearance", kind="write"),
    Permission.APPEARANCE_FAVICON_DELETE: PermissionMeta(resource="appearance", kind="write"),
    Permission.GATEWAYS_VIEW: PermissionMeta(resource="gateways", kind="read"),
    Permission.GATEWAYS_UPDATE: PermissionMeta(resource="gateways", kind="write"),
    Permission.GATEWAYS_ACTIVE_SET: PermissionMeta(resource="gateways", kind="write"),
    Permission.GATEWAYS_REORDER: PermissionMeta(resource="gateways", kind="write"),
    Permission.GATEWAYS_TEST: PermissionMeta(resource="gateways", kind="write"),
    Permission.GATEWAYS_TEST_VIEW: PermissionMeta(resource="gateways", kind="read"),
    Permission.PLANS_VIEW: PermissionMeta(resource="plans", kind="read"),
    Permission.PLANS_DETAIL_VIEW: PermissionMeta(resource="plans", kind="read"),
    Permission.PLANS_SHARE_VIEW: PermissionMeta(resource="plans", kind="read"),
    Permission.PLANS_CREATE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_UPDATE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_DELETE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_DURATIONS_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_PRICE_OVERRIDE_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_DURATION_BASE_PRICE_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_ACCESS_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_SQUADS_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_DISCOUNT_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_ORDER_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PRICING_VIEW: PermissionMeta(resource="pricing", kind="read"),
    Permission.PRICING_PREVIEW_VIEW: PermissionMeta(resource="pricing", kind="read"),
    Permission.PRICING_SETTINGS_MANAGE: PermissionMeta(resource="pricing", kind="write"),
    Permission.PRICING_BASE_ADJUST_MANAGE: PermissionMeta(resource="pricing", kind="write"),
    Permission.SUBSCRIPTIONS_VIEW: PermissionMeta(resource="subscriptions", kind="read"),
    Permission.SUBSCRIPTIONS_DETAIL_VIEW: PermissionMeta(resource="subscriptions", kind="read"),
    Permission.SUBSCRIPTIONS_UPDATE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_SQUADS_MANAGE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_DELETE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_GRANT: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_PLAN_CHANGE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_STATUS_MANAGE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_TRAFFIC_RESET: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_LINK_REISSUE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_DEVICES_VIEW: PermissionMeta(resource="subscriptions", kind="read"),
    Permission.SUBSCRIPTIONS_DEVICES_DELETE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_DEVICES_DELETE_ALL: PermissionMeta(
        resource="subscriptions", kind="write"
    ),
    Permission.SUBSCRIPTIONS_PANEL_DIFF_VIEW: PermissionMeta(resource="subscriptions", kind="read"),
    Permission.SUBSCRIPTIONS_PULL_FROM_PANEL: PermissionMeta(
        resource="subscriptions", kind="write"
    ),
    Permission.SUBSCRIPTIONS_PUSH_TO_PANEL: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_PANEL_SYNC_STATUS_VIEW: PermissionMeta(
        resource="subscriptions", kind="read"
    ),
    Permission.SUBSCRIPTIONS_PANEL_SYNC_FROM: PermissionMeta(
        resource="subscriptions", kind="write"
    ),
    Permission.SUBSCRIPTIONS_PANEL_SYNC_TO: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.ADDONS_VIEW: PermissionMeta(resource="addons", kind="read"),
    Permission.ADDONS_DETAIL_VIEW: PermissionMeta(resource="addons", kind="read"),
    Permission.ADDONS_CREATE: PermissionMeta(resource="addons", kind="write"),
    Permission.ADDONS_UPDATE: PermissionMeta(resource="addons", kind="write"),
    Permission.ADDONS_DELETE: PermissionMeta(resource="addons", kind="write"),
    Permission.ADDONS_PRICES_MANAGE: PermissionMeta(resource="addons", kind="write"),
    Permission.ADDONS_PRICE_OVERRIDE_MANAGE: PermissionMeta(resource="addons", kind="write"),
    Permission.PROMOCODES_VIEW: PermissionMeta(resource="promocodes", kind="read"),
    Permission.PROMOCODES_DETAIL_VIEW: PermissionMeta(resource="promocodes", kind="read"),
    Permission.PROMOCODES_ACTIVATIONS_VIEW: PermissionMeta(resource="promocodes", kind="read"),
    Permission.PROMOCODES_SUMMARY_VIEW: PermissionMeta(resource="promocodes", kind="read"),
    Permission.PROMOCODES_USERS_VIEW: PermissionMeta(resource="promocodes", kind="read"),
    Permission.PROMOCODES_CREATE: PermissionMeta(resource="promocodes", kind="write"),
    Permission.PROMOCODES_UPDATE: PermissionMeta(resource="promocodes", kind="write"),
    Permission.PROMOCODES_DELETE: PermissionMeta(resource="promocodes", kind="write"),
    Permission.PROMOCODES_GENERATE_CODE: PermissionMeta(resource="promocodes", kind="write"),
    Permission.BROADCASTS_VIEW: PermissionMeta(resource="broadcasts", kind="read"),
    Permission.BROADCASTS_DETAIL_VIEW: PermissionMeta(resource="broadcasts", kind="read"),
    Permission.BROADCASTS_CREATE: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_UPDATE: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_DELETE: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_SEND: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_RECALL: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_CANCEL: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_RETRY: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_TEST_SEND: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_RECIPIENTS_VIEW: PermissionMeta(resource="broadcasts", kind="read"),
    Permission.BROADCASTS_MEDIA_SET: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_MEDIA_DELETE: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_AUDIENCE_PREVIEW: PermissionMeta(resource="broadcasts", kind="read"),
    Permission.BROADCASTS_SUMMARY_VIEW: PermissionMeta(resource="broadcasts", kind="read"),
    Permission.BROADCASTS_EMAIL_IMAGE_ADD: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.BROADCASTS_EMAIL_IMAGE_VIEW: PermissionMeta(resource="broadcasts", kind="read"),
    Permission.BROADCASTS_EMAIL_PREVIEW: PermissionMeta(resource="broadcasts", kind="read"),
    Permission.BROADCASTS_EMAIL_TEST_SEND: PermissionMeta(resource="broadcasts", kind="write"),
    Permission.TRANSACTIONS_VIEW: PermissionMeta(resource="transactions", kind="read"),
    Permission.TRANSACTIONS_SUMMARY_VIEW: PermissionMeta(resource="transactions", kind="read"),
    Permission.TRANSACTIONS_DETAIL_VIEW: PermissionMeta(resource="transactions", kind="read"),
    Permission.TRANSACTIONS_GATEWAYS_VIEW: PermissionMeta(resource="transactions", kind="read"),
    Permission.TRANSACTIONS_FULFILL: PermissionMeta(resource="transactions", kind="write"),
    Permission.TRANSACTIONS_REFUND: PermissionMeta(resource="transactions", kind="write"),
    Permission.TRANSACTIONS_REFUND_PREVIEW: PermissionMeta(resource="transactions", kind="read"),
    Permission.REFERRALS_VIEW: PermissionMeta(resource="referrals", kind="read"),
    Permission.REFERRALS_INVITED_VIEW: PermissionMeta(resource="referrals", kind="read"),
    Permission.REFERRALS_REVENUE_VIEW: PermissionMeta(resource="referrals", kind="read"),
    Permission.REFERRALS_LIST: PermissionMeta(resource="referrals", kind="read"),
    Permission.REFERRALS_SUMMARY_VIEW: PermissionMeta(resource="referrals", kind="read"),
    Permission.REFERRALS_SETTINGS_VIEW: PermissionMeta(resource="referrals", kind="read"),
    Permission.REFERRALS_SETTINGS_MANAGE: PermissionMeta(resource="referrals", kind="write"),
    Permission.REFERRALS_SETTINGS_RESET: PermissionMeta(resource="referrals", kind="write"),
    Permission.REFERRALS_POINTS_MANAGE: PermissionMeta(resource="referrals", kind="write"),
    Permission.REFERRALS_BONUS_DAYS_MANAGE: PermissionMeta(resource="referrals", kind="write"),
    Permission.REFERRALS_CODE_RESET: PermissionMeta(resource="referrals", kind="write"),
    Permission.LOYALTY_SETTINGS_VIEW: PermissionMeta(resource="loyalty", kind="read"),
    Permission.LOYALTY_SETTINGS_MANAGE: PermissionMeta(resource="loyalty", kind="write"),
    Permission.LOYALTY_SETTINGS_RESET: PermissionMeta(resource="loyalty", kind="write"),
    Permission.BACKUPS_VIEW: PermissionMeta(resource="backups", kind="read"),
    Permission.BACKUPS_SETTINGS_VIEW: PermissionMeta(resource="backups", kind="read"),
    Permission.BACKUPS_SETTINGS_MANAGE: PermissionMeta(resource="backups", kind="write"),
    Permission.BACKUPS_SETTINGS_RESET: PermissionMeta(resource="backups", kind="write"),
    Permission.BACKUPS_RUN_VIEW: PermissionMeta(resource="backups", kind="read"),
    Permission.BACKUPS_RUN_CREATE: PermissionMeta(resource="backups", kind="write"),
    Permission.BACKUPS_RUN_DELETE: PermissionMeta(resource="backups", kind="write"),
    Permission.BACKUPS_STATS_VIEW: PermissionMeta(resource="backups", kind="read"),
    Permission.BLACKLIST_VIEW: PermissionMeta(resource="blacklist", kind="read"),
    Permission.BLACKLIST_SOURCES_VIEW: PermissionMeta(resource="blacklist", kind="read"),
    Permission.BLACKLIST_SOURCE_DETAIL_VIEW: PermissionMeta(resource="blacklist", kind="read"),
    Permission.BLACKLIST_ENTRY_ADD: PermissionMeta(resource="blacklist", kind="write"),
    Permission.BLACKLIST_ENTRY_REMOVE: PermissionMeta(resource="blacklist", kind="write"),
    Permission.BLACKLIST_SOURCE_ADD: PermissionMeta(resource="blacklist", kind="write"),
    Permission.BLACKLIST_SOURCE_REMOVE: PermissionMeta(resource="blacklist", kind="write"),
    Permission.BLACKLIST_SOURCE_UPDATE: PermissionMeta(resource="blacklist", kind="write"),
    Permission.BLACKLIST_SYNC: PermissionMeta(resource="blacklist", kind="write"),
    Permission.BLACKLIST_MATCHES_VIEW: PermissionMeta(resource="blacklist", kind="read"),
    Permission.USERS_BLOCK: PermissionMeta(resource="users", kind="write"),
    Permission.USERS_EMAIL_UNDELIVERABLE_CLEAR: PermissionMeta(resource="users", kind="write"),
    Permission.USERS_UNBLOCK: PermissionMeta(resource="users", kind="write"),
    Permission.USERS_MERGE_PREVIEW: PermissionMeta(resource="users", kind="read"),
    Permission.USERS_MERGE: PermissionMeta(resource="users", kind="write"),
    Permission.USERS_TELEGRAM_BIND: PermissionMeta(resource="users", kind="write"),
    Permission.AD_LINKS_VIEW: PermissionMeta(resource="ad_links", kind="read"),
    Permission.AD_LINKS_DETAIL_VIEW: PermissionMeta(resource="ad_links", kind="read"),
    Permission.AD_LINKS_STATS_VIEW: PermissionMeta(resource="ad_links", kind="read"),
    Permission.AD_LINKS_SUMMARY_VIEW: PermissionMeta(resource="ad_links", kind="read"),
    Permission.AD_LINKS_USERS_VIEW: PermissionMeta(resource="ad_links", kind="read"),
    Permission.AD_LINKS_USER_ATTRIBUTION_VIEW: PermissionMeta(resource="ad_links", kind="read"),
    Permission.AD_LINKS_SHARE_VIEW: PermissionMeta(resource="ad_links", kind="read"),
    Permission.AD_LINKS_CREATE: PermissionMeta(resource="ad_links", kind="write"),
    Permission.AD_LINKS_GENERATE_CODE: PermissionMeta(resource="ad_links", kind="write"),
    Permission.AD_LINKS_UPDATE: PermissionMeta(resource="ad_links", kind="write"),
    Permission.AD_LINKS_DELETE: PermissionMeta(resource="ad_links", kind="write"),
    Permission.ANALYTICS_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.ANALYTICS_FUNNEL_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.ANALYTICS_COHORTS_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.ANALYTICS_LTV_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.ANALYTICS_LTV_BREAKDOWN_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.ANALYTICS_REVENUE_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.ANALYTICS_TRIAL_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.ANALYTICS_RETENTION_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.ANALYTICS_SOURCES_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.ANALYTICS_PROMOCODES_VIEW: PermissionMeta(resource="analytics", kind="read"),
    Permission.REMNAWAVE_NODES_VIEW: PermissionMeta(resource="remnawave", kind="read"),
    Permission.REMNAWAVE_CLIENT_APPS_VIEW: PermissionMeta(resource="remnawave", kind="read"),
}

GRANTABLE_PERMISSIONS: Final[frozenset[Permission]] = frozenset(PERMISSION_METADATA)

# A token is a bearer string living in a script: it can't take over a login,
# the bot or the payment flow, and can't wipe data in bulk.
_TOKEN_EXCLUDED_PERMISSIONS: Final[frozenset[Permission]] = frozenset(
    {
        # login methods: an issuer of one's own logs in as any linked identity
        Permission.OAUTH_SETTINGS_MANAGE,
        # SMTP credentials and the server login codes are mailed through
        Permission.EMAIL_SETTINGS_MANAGE,
        # bot token and the proxy every Telegram call (token in its URL) goes through
        Permission.BOT_SETTINGS_MANAGE,
        Permission.BOT_PROXY_SET,
        # merchant credentials: payments land in another account
        Permission.GATEWAYS_UPDATE,
        Permission.GATEWAYS_ACTIVE_SET,
        # provisions an order nobody was paid for
        Permission.TRANSACTIONS_FULFILL,
        # sends money back
        Permission.TRANSACTIONS_REFUND,
        Permission.TRANSACTIONS_REFUND_PREVIEW,
        # who gets alerted, and from where
        Permission.NOTIFICATION_SETTINGS_MANAGE,
        # irreversible or bulk
        Permission.BACKUPS_SETTINGS_MANAGE,
        Permission.BACKUPS_RUN_DELETE,
        # reset shrinks retention and a run rotates old backups away
        Permission.BACKUPS_SETTINGS_RESET,
        Permission.BACKUPS_RUN_CREATE,
        Permission.BLACKLIST_SOURCE_ADD,
        Permission.BLACKLIST_SYNC,
        Permission.USERS_DELETE,
        Permission.USERS_MERGE,
        Permission.USERS_MERGE_PREVIEW,
        # a Telegram id is how a customer logs into the bot
        Permission.USERS_TELEGRAM_BIND,
        Permission.SUBSCRIPTIONS_LINK_REISSUE,
        Permission.SUBSCRIPTIONS_DEVICES_DELETE,
        Permission.SUBSCRIPTIONS_DEVICES_DELETE_ALL,
        # every subscription at once, one side overwriting the other
        Permission.SUBSCRIPTIONS_PANEL_SYNC_FROM,
        Permission.SUBSCRIPTIONS_PANEL_SYNC_TO,
        Permission.TRANSLATIONS_IMPORT,
        Permission.TRANSLATIONS_RESET_ALL,
        Permission.DIALOGS_IMPORT,
        Permission.DIALOGS_WINDOWS_RESET_ALL,
        Permission.BROADCASTS_SEND,
        Permission.BROADCASTS_RECALL,
        Permission.BROADCASTS_RETRY,
        Permission.BROADCASTS_DELETE,
    }
)

TOKEN_GRANTABLE_PERMISSIONS: Final[frozenset[Permission]] = (
    GRANTABLE_PERMISSIONS - _TOKEN_EXCLUDED_PERMISSIONS
)

TOKEN_SCOPE_WILDCARD: Final[str] = "*"


def expand_token_scopes(scopes: list[str]) -> set[Permission]:
    """Scopes: `*`, `<resource>:*`, `<resource>:read|write`, or a
    single permission. Expanded on every request, so a permission added to a
    resource later reaches tokens scoped to it, and an exclusion reaches every
    token at once."""
    granted: set[Permission] = set()
    for scope in scopes:
        if scope == TOKEN_SCOPE_WILDCARD:
            return set(TOKEN_GRANTABLE_PERMISSIONS)
        resource, separator, action = scope.partition(":")
        if separator:
            granted |= {
                permission
                for permission in TOKEN_GRANTABLE_PERMISSIONS
                if PERMISSION_METADATA[permission].resource == resource
                and action in (TOKEN_SCOPE_WILDCARD, PERMISSION_METADATA[permission].kind)
            }
        elif scope in Permission and Permission(scope) in TOKEN_GRANTABLE_PERMISSIONS:
            granted.add(Permission(scope))
    return granted


def assert_token_scopes(scopes: list[str]) -> None:
    # a scope granting nothing is a typo or an excluded permission
    invalid = [scope for scope in scopes if not expand_token_scopes([scope])]
    if invalid:
        raise ValidationError(
            f"Not grantable to an API token: {', '.join(sorted(invalid))}",
            code=ErrorCode.PERMISSION_NOT_GRANTABLE,
        )


ROLE_PERMISSIONS: Final[dict[Role, frozenset[Permission]]] = {
    Role.SYSTEM: frozenset(Permission),
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset(
        {
            Permission.BOT_SETTINGS_VIEW,
            Permission.BOT_STATUS_VIEW,
            Permission.BOT_LOGS_VIEW,
            Permission.BOT_COMMANDS_VIEW,
            Permission.BOT_SETTINGS_MANAGE,
            Permission.BOT_COMMANDS_MANAGE,
            Permission.BOT_REQUIREMENTS_VIEW,
            Permission.BOT_REQUIREMENTS_MANAGE,
            Permission.BOT_RESTART,
            Permission.BOT_PROXY_SET,
            Permission.BOT_PROXY_REMOVE,
            Permission.SHOP_SETTINGS_VIEW,
            Permission.SHOP_SETTINGS_MANAGE,
            Permission.ACCESS_SETTINGS_VIEW,
            Permission.ACCESS_SETTINGS_MANAGE,
            Permission.PAYMENT_WAITLIST_VIEW,
            Permission.BANNERS_IMAGE_VIEW,
            Permission.BANNERS_UPLOAD,
            Permission.BANNERS_DELETE,
            Permission.BANNERS_RESTORE_DEFAULT,
            Permission.LEGAL_DOCUMENTS_VIEW,
            Permission.LEGAL_DOCUMENTS_UPDATE,
            Permission.LEGAL_TEXT_SET,
            Permission.LEGAL_TEXT_REMOVE,
            Permission.LEGAL_ACCEPTANCES_VIEW,
            Permission.EMOJI_PACKS_VIEW,
            Permission.EMOJI_PACKS_IMPORT,
            Permission.EMOJI_PACKS_DELETE,
            Permission.OAUTH_SETTINGS_VIEW,
            Permission.EMAIL_SETTINGS_VIEW,
            Permission.EMAIL_SETTINGS_TEST,
            Permission.EMAIL_SETTINGS_BULK_RESET,
            Permission.CABINET_AUTH_SETTINGS_VIEW,
            Permission.CABINET_AUTH_SETTINGS_MANAGE,
            Permission.LOCALES_VIEW,
            Permission.LOCALES_ADD,
            Permission.LOCALES_REMOVE,
            Permission.LOCALES_DEFAULT_SET,
            Permission.TRANSLATIONS_VIEW,
            Permission.TRANSLATIONS_UPDATE,
            Permission.TRANSLATIONS_RESET,
            Permission.TRANSLATIONS_RESET_ALL,
            Permission.TRANSLATIONS_EXPORT,
            Permission.TRANSLATIONS_IMPORT,
            Permission.DIALOGS_WINDOWS_VIEW,
            Permission.DIALOGS_CATALOG_VIEW,
            Permission.DIALOGS_WINDOWS_UPDATE,
            Permission.DIALOGS_WINDOWS_BUTTONS_UPDATE,
            Permission.DIALOGS_WINDOWS_CREATE,
            Permission.DIALOGS_WINDOWS_DELETE,
            Permission.DIALOGS_WINDOWS_RESET,
            Permission.DIALOGS_WINDOWS_RESET_ALL,
            Permission.DIALOGS_TEXT_UPDATE,
            Permission.DIALOGS_EXPORT,
            Permission.DIALOGS_IMPORT,
            Permission.OWN_ACCOUNT_MANAGE,
            Permission.PLANS_VIEW,
            Permission.PLANS_DETAIL_VIEW,
            Permission.PLANS_SHARE_VIEW,
            Permission.PLANS_CREATE,
            Permission.PLANS_UPDATE,
            Permission.PLANS_DELETE,
            Permission.PLANS_DURATIONS_MANAGE,
            Permission.PLANS_PRICE_OVERRIDE_MANAGE,
            Permission.PLANS_DURATION_BASE_PRICE_MANAGE,
            Permission.PLANS_ACCESS_MANAGE,
            Permission.PLANS_SQUADS_MANAGE,
            Permission.PLANS_DISCOUNT_MANAGE,
            Permission.PLANS_ORDER_MANAGE,
            Permission.PRICING_VIEW,
            Permission.PRICING_PREVIEW_VIEW,
            Permission.PRICING_SETTINGS_MANAGE,
            Permission.PRICING_BASE_ADJUST_MANAGE,
            Permission.SUBSCRIPTIONS_VIEW,
            Permission.SUBSCRIPTIONS_DETAIL_VIEW,
            Permission.SUBSCRIPTIONS_UPDATE,
            Permission.SUBSCRIPTIONS_SQUADS_MANAGE,
            Permission.SUBSCRIPTIONS_DELETE,
            Permission.SUBSCRIPTIONS_GRANT,
            Permission.SUBSCRIPTIONS_PLAN_CHANGE,
            Permission.SUBSCRIPTIONS_STATUS_MANAGE,
            Permission.SUBSCRIPTIONS_TRAFFIC_RESET,
            Permission.SUBSCRIPTIONS_LINK_REISSUE,
            Permission.SUBSCRIPTIONS_DEVICES_VIEW,
            Permission.SUBSCRIPTIONS_DEVICES_DELETE,
            Permission.SUBSCRIPTIONS_DEVICES_DELETE_ALL,
            Permission.SUBSCRIPTIONS_PANEL_DIFF_VIEW,
            Permission.SUBSCRIPTIONS_PULL_FROM_PANEL,
            Permission.SUBSCRIPTIONS_PUSH_TO_PANEL,
            Permission.SUBSCRIPTIONS_PANEL_SYNC_STATUS_VIEW,
            Permission.SUBSCRIPTIONS_PANEL_SYNC_FROM,
            Permission.SUBSCRIPTIONS_PANEL_SYNC_TO,
            Permission.ADDONS_VIEW,
            Permission.ADDONS_DETAIL_VIEW,
            Permission.ADDONS_CREATE,
            Permission.ADDONS_UPDATE,
            Permission.ADDONS_DELETE,
            Permission.ADDONS_PRICES_MANAGE,
            Permission.ADDONS_PRICE_OVERRIDE_MANAGE,
            Permission.PROMOCODES_VIEW,
            Permission.PROMOCODES_DETAIL_VIEW,
            Permission.PROMOCODES_CREATE,
            Permission.PROMOCODES_UPDATE,
            Permission.PROMOCODES_DELETE,
            Permission.PROMOCODES_GENERATE_CODE,
            Permission.PROMOCODES_ACTIVATIONS_VIEW,
            Permission.PROMOCODES_SUMMARY_VIEW,
            Permission.PROMOCODES_USERS_VIEW,
            Permission.BROADCASTS_VIEW,
            Permission.BROADCASTS_DETAIL_VIEW,
            Permission.BROADCASTS_CREATE,
            Permission.BROADCASTS_UPDATE,
            Permission.BROADCASTS_DELETE,
            Permission.BROADCASTS_SEND,
            Permission.BROADCASTS_RECALL,
            Permission.BROADCASTS_CANCEL,
            Permission.BROADCASTS_RETRY,
            Permission.BROADCASTS_TEST_SEND,
            Permission.BROADCASTS_RECIPIENTS_VIEW,
            Permission.BROADCASTS_MEDIA_SET,
            Permission.BROADCASTS_MEDIA_DELETE,
            Permission.BROADCASTS_AUDIENCE_PREVIEW,
            Permission.BROADCASTS_SUMMARY_VIEW,
            Permission.BROADCASTS_EMAIL_IMAGE_ADD,
            Permission.BROADCASTS_EMAIL_IMAGE_VIEW,
            Permission.BROADCASTS_EMAIL_PREVIEW,
            Permission.BROADCASTS_EMAIL_TEST_SEND,
            Permission.USERS_VIEW,
            Permission.USERS_DETAIL_VIEW,
            Permission.USERS_REGISTRATION_VIEW,
            Permission.USERS_DISCOUNT_MANAGE,
            Permission.USERS_EMAIL_UNDELIVERABLE_CLEAR,
            Permission.USERS_LOYALTY_VIEW,
            Permission.USERS_LOYALTY_MANAGE,
            Permission.TRANSACTIONS_VIEW,
            Permission.TRANSACTIONS_SUMMARY_VIEW,
            Permission.TRANSACTIONS_DETAIL_VIEW,
            Permission.TRANSACTIONS_GATEWAYS_VIEW,
            Permission.TRANSACTIONS_FULFILL,
            Permission.REFERRALS_VIEW,
            Permission.REFERRALS_INVITED_VIEW,
            Permission.REFERRALS_REVENUE_VIEW,
            Permission.REFERRALS_LIST,
            Permission.REFERRALS_SUMMARY_VIEW,
            Permission.REFERRALS_SETTINGS_VIEW,
            Permission.REFERRALS_SETTINGS_MANAGE,
            Permission.REFERRALS_SETTINGS_RESET,
            Permission.REFERRALS_POINTS_MANAGE,
            Permission.REFERRALS_BONUS_DAYS_MANAGE,
            Permission.REFERRALS_CODE_RESET,
            Permission.LOYALTY_SETTINGS_VIEW,
            Permission.LOYALTY_SETTINGS_MANAGE,
            Permission.LOYALTY_SETTINGS_RESET,
            Permission.AD_LINKS_VIEW,
            Permission.AD_LINKS_DETAIL_VIEW,
            Permission.AD_LINKS_STATS_VIEW,
            Permission.AD_LINKS_SUMMARY_VIEW,
            Permission.AD_LINKS_USERS_VIEW,
            Permission.AD_LINKS_USER_ATTRIBUTION_VIEW,
            Permission.AD_LINKS_SHARE_VIEW,
            Permission.AD_LINKS_CREATE,
            Permission.AD_LINKS_GENERATE_CODE,
            Permission.AD_LINKS_UPDATE,
            Permission.AD_LINKS_DELETE,
            Permission.ANALYTICS_VIEW,
            Permission.ANALYTICS_FUNNEL_VIEW,
            Permission.ANALYTICS_COHORTS_VIEW,
            Permission.ANALYTICS_LTV_VIEW,
            Permission.ANALYTICS_LTV_BREAKDOWN_VIEW,
            Permission.ANALYTICS_REVENUE_VIEW,
            Permission.ANALYTICS_TRIAL_VIEW,
            Permission.ANALYTICS_RETENTION_VIEW,
            Permission.ANALYTICS_SOURCES_VIEW,
            Permission.ANALYTICS_PROMOCODES_VIEW,
            Permission.REMNAWAVE_NODES_VIEW,
            Permission.REMNAWAVE_CLIENT_APPS_VIEW,
        }
    ),
    Role.USER: frozenset(),
}


def assert_grantable(
    permissions: list[Permission], allowed: frozenset[Permission] = GRANTABLE_PERMISSIONS
) -> None:
    non_grantable = set(permissions) - allowed
    if non_grantable:
        names = ", ".join(sorted(p.value for p in non_grantable))
        raise ValidationError(
            f"Not grantable via permission overrides: {names}",
            code=ErrorCode.PERMISSION_NOT_GRANTABLE,
        )


class PermissionPolicy:
    @staticmethod
    def effective_permissions(actor: Actor) -> set[Permission]:
        if actor.is_system:
            return set(Permission)

        base = set(ROLE_PERMISSIONS.get(actor.role, frozenset()))
        grants = {Permission(p) for p in (actor.permission_grants or []) if p in Permission}
        revokes = {Permission(p) for p in (actor.permission_revokes or []) if p in Permission}
        return (base | grants) - revokes

    @staticmethod
    def can_manage(actor: Actor, target: Actor) -> bool:
        # customers are within anyone's reach, staff only from a strictly higher
        # role; an API token carries Role.USER, so staff stay out of its reach
        return not target.is_privileged or actor.role > target.role

    @staticmethod
    def has_permission(actor: Actor, permission: "Permission") -> bool:
        if permission is Permission.PUBLIC:
            return True
        return permission in PermissionPolicy.effective_permissions(actor)
