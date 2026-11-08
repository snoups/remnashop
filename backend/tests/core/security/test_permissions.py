import pytest

from app.core.actor import SYSTEM_ACTOR, Actor, SyntheticActor
from app.core.enums import Locale, Role
from app.core.exceptions import ValidationError
from app.core.security.permissions import (
    GRANTABLE_PERMISSIONS,
    PERMISSION_METADATA,
    ROLE_PERMISSIONS,
    TOKEN_GRANTABLE_PERMISSIONS,
    Permission,
    PermissionPolicy,
    assert_grantable,
    expand_token_scopes,
)
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
ADMIN = UserDto(id=2, login="admin", name="admin", role=Role.ADMIN, language=Locale.EN)
REGULAR_USER = UserDto(id=3, name="Bob", role=Role.USER, language=Locale.EN)


def test_owner_has_manage_admins_by_default() -> None:
    assert PermissionPolicy.has_permission(OWNER, Permission.ADMINS_MANAGE)


def test_admin_does_not_have_manage_admins_by_default() -> None:
    assert not PermissionPolicy.has_permission(ADMIN, Permission.ADMINS_MANAGE)


def test_admin_gains_permission_via_grant() -> None:
    granted_admin = ADMIN.model_copy(update={"permission_grants": ["ADMINS_MANAGE"]})
    assert PermissionPolicy.has_permission(granted_admin, Permission.ADMINS_MANAGE)


def test_admin_loses_default_permission_via_revoke() -> None:
    revoked_admin = ADMIN.model_copy(update={"permission_revokes": ["BOT_SETTINGS_MANAGE"]})
    assert not PermissionPolicy.has_permission(revoked_admin, Permission.BOT_SETTINGS_MANAGE)


def test_manage_admins_is_not_grantable() -> None:
    assert Permission.ADMINS_MANAGE not in GRANTABLE_PERMISSIONS


def test_assert_grantable_rejects_manage_admins() -> None:
    with pytest.raises(ValidationError):
        assert_grantable([Permission.ADMINS_MANAGE])


def test_assert_grantable_allows_ordinary_permissions() -> None:
    assert_grantable([Permission.BOT_SETTINGS_MANAGE])  # does not raise


def test_regular_user_has_no_permissions_by_default() -> None:
    assert not PermissionPolicy.has_permission(REGULAR_USER, Permission.OWN_ACCOUNT_MANAGE)


def test_effective_permissions_drops_stale_grant_string() -> None:
    stale_admin = ADMIN.model_copy(update={"permission_grants": ["SOME_REMOVED_PERMISSION"]})
    effective = PermissionPolicy.effective_permissions(stale_admin)
    assert effective == ROLE_PERMISSIONS[Role.ADMIN]


def test_effective_permissions_drops_stale_revoke_string() -> None:
    stale_admin = ADMIN.model_copy(update={"permission_revokes": ["SOME_REMOVED_PERMISSION"]})
    effective = PermissionPolicy.effective_permissions(stale_admin)
    assert effective == ROLE_PERMISSIONS[Role.ADMIN]


def test_view_event_log_is_grantable() -> None:
    assert Permission.EVENT_LOG_VIEW in GRANTABLE_PERMISSIONS


def test_owner_has_view_event_log_by_default() -> None:
    assert PermissionPolicy.has_permission(OWNER, Permission.EVENT_LOG_VIEW)


def test_admin_does_not_have_view_event_log_by_default() -> None:
    assert not PermissionPolicy.has_permission(ADMIN, Permission.EVENT_LOG_VIEW)


def test_admin_gains_view_event_log_via_grant() -> None:
    granted_admin = ADMIN.model_copy(update={"permission_grants": ["EVENT_LOG_VIEW"]})
    assert PermissionPolicy.has_permission(granted_admin, Permission.EVENT_LOG_VIEW)


def test_view_users_is_grantable() -> None:
    assert Permission.USERS_VIEW in GRANTABLE_PERMISSIONS


def test_owner_has_view_users_by_default() -> None:
    assert PermissionPolicy.has_permission(OWNER, Permission.USERS_VIEW)


def test_admin_has_view_users_by_default() -> None:
    assert PermissionPolicy.has_permission(ADMIN, Permission.USERS_VIEW)


def test_delete_user_is_grantable() -> None:
    assert Permission.USERS_DELETE in GRANTABLE_PERMISSIONS


def test_owner_has_delete_user_by_default() -> None:
    assert PermissionPolicy.has_permission(OWNER, Permission.USERS_DELETE)


def test_admin_does_not_have_delete_user_by_default() -> None:
    assert not PermissionPolicy.has_permission(ADMIN, Permission.USERS_DELETE)


def test_admin_gains_delete_user_via_grant() -> None:
    granted_admin = ADMIN.model_copy(update={"permission_grants": ["USERS_DELETE"]})
    assert PermissionPolicy.has_permission(granted_admin, Permission.USERS_DELETE)


def test_manage_api_tokens_is_not_grantable() -> None:
    assert Permission.API_TOKENS_MANAGE not in GRANTABLE_PERMISSIONS


def test_assert_grantable_rejects_manage_api_tokens() -> None:
    with pytest.raises(ValidationError):
        assert_grantable([Permission.API_TOKENS_MANAGE])


def test_owner_has_manage_api_tokens_by_default() -> None:
    assert PermissionPolicy.has_permission(OWNER, Permission.API_TOKENS_MANAGE)


def test_admin_does_not_have_manage_api_tokens_by_default() -> None:
    assert not PermissionPolicy.has_permission(ADMIN, Permission.API_TOKENS_MANAGE)


def test_manage_own_account_is_not_grantable() -> None:
    # every privileged role has it by default, and revoking it breaks GET /users/me
    assert Permission.OWN_ACCOUNT_MANAGE not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.OWN_ACCOUNT_MANAGE not in GRANTABLE_PERMISSIONS


def test_every_catalog_permission_has_metadata() -> None:
    non_catalog = {
        Permission.PUBLIC,
        Permission.OWN_ACCOUNT_MANAGE,
        Permission.ADMINS_MANAGE,
        Permission.API_TOKENS_MANAGE,
        Permission.PRICING_RATES_MANAGE,
        Permission.PRICING_ANCHOR_MANAGE,
        Permission.TRANSACTIONS_UNRATED_RATE,
        Permission.USERS_UNBLOCK_BLACKLIST_MATCHES,
        Permission.BACKUPS_RUN_DOWNLOAD,
        Permission.NOTIFICATION_VAPID_KEYS_GENERATE,
        Permission.OVERVIEW_RECAP_VIEW,
    }
    assert set(Permission) - PERMISSION_METADATA.keys() == non_catalog


def test_role_permissions_admin_matches_expected_defaults() -> None:
    assert ROLE_PERMISSIONS[Role.ADMIN] == {
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
        Permission.EMAIL_SETTINGS_RESET,
        Permission.CABINET_AUTH_SETTINGS_VIEW,
        Permission.CABINET_AUTH_SETTINGS_MANAGE,
        Permission.CONNECT_GUIDE_VIEW,
        Permission.CONNECT_GUIDE_MANAGE,
        Permission.CONNECT_GUIDE_RESET,
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
        Permission.DIALOGS_EXPORT,
        Permission.DIALOGS_IMPORT,
        Permission.DIALOGS_WINDOWS_UPDATE,
        Permission.DIALOGS_WINDOWS_BUTTONS_UPDATE,
        Permission.DIALOGS_WINDOWS_CREATE,
        Permission.DIALOGS_WINDOWS_DELETE,
        Permission.DIALOGS_WINDOWS_RESET,
        Permission.DIALOGS_WINDOWS_RESET_ALL,
        Permission.DIALOGS_TEXT_UPDATE,
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
        Permission.PRICING_MATRIX_MANAGE,
        Permission.SUBSCRIPTIONS_VIEW,
        Permission.SUBSCRIPTIONS_DETAIL_VIEW,
        Permission.SUBSCRIPTIONS_STATS_VIEW,
        Permission.SUBSCRIPTIONS_UPDATE,
        Permission.SUBSCRIPTIONS_SQUADS_MANAGE,
        Permission.SUBSCRIPTIONS_DELETE,
        Permission.SUBSCRIPTIONS_DELETE_ALL,
        Permission.SUBSCRIPTIONS_GRANT,
        Permission.SUBSCRIPTIONS_PLAN_CHANGE,
        Permission.SUBSCRIPTIONS_STATUS_MANAGE,
        Permission.SUBSCRIPTIONS_TRAFFIC_RESET,
        Permission.SUBSCRIPTIONS_LINK_REISSUE,
        Permission.SUBSCRIPTIONS_DEVICES_VIEW,
        Permission.SUBSCRIPTIONS_DEVICES_DELETE,
        Permission.SUBSCRIPTIONS_DEVICES_DELETE_ALL,
        Permission.SUBSCRIPTIONS_PANEL_DIFF_VIEW,
        Permission.SUBSCRIPTIONS_PANEL_SQUADS_VIEW,
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
        Permission.USERS_TRIAL_MANAGE,
        Permission.USERS_LOYALTY_VIEW,
        Permission.USERS_LOYALTY_MANAGE,
        Permission.TRANSACTIONS_VIEW,
        Permission.TRANSACTIONS_SUMMARY_VIEW,
        Permission.TRANSACTIONS_DETAIL_VIEW,
        Permission.TRANSACTIONS_GATEWAYS_VIEW,
        Permission.TRANSACTIONS_FULFILL,
        Permission.TRANSACTIONS_UNRATED_VIEW,
        Permission.REFERRALS_VIEW,
        Permission.REFERRALS_INVITED_VIEW,
        Permission.REFERRALS_REWARDS_VIEW,
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
        Permission.ANALYTICS_EXPIRING_VIEW,
        Permission.ANALYTICS_SOURCES_VIEW,
        Permission.ANALYTICS_PROMOCODES_VIEW,
        Permission.REMNAWAVE_NODES_VIEW,
        Permission.REMNAWAVE_CLIENT_APPS_VIEW,
    }


def test_user_sessions_revoke_is_distinct_from_view() -> None:
    assert Permission.USER_SESSIONS_REVOKE != Permission.USER_SESSIONS_VIEW
    granted_view_only = ADMIN.model_copy(
        update={"permission_grants": [Permission.USER_SESSIONS_VIEW.value]}
    )
    assert not PermissionPolicy.has_permission(granted_view_only, Permission.USER_SESSIONS_REVOKE)


def test_banner_permissions_are_independently_gateable() -> None:
    # ADMIN has every banner permission by default; revoke two, BANNERS_UPLOAD stays
    upload_only = ADMIN.model_copy(
        update={
            "permission_revokes": [
                Permission.BANNERS_IMAGE_VIEW.value,
                Permission.BANNERS_DELETE.value,
            ]
        }
    )
    assert PermissionPolicy.has_permission(upload_only, Permission.BANNERS_UPLOAD)
    assert not PermissionPolicy.has_permission(upload_only, Permission.BANNERS_DELETE)
    assert not PermissionPolicy.has_permission(upload_only, Permission.BANNERS_IMAGE_VIEW)


def test_gateways_permissions_are_grantable() -> None:
    assert Permission.GATEWAYS_VIEW in GRANTABLE_PERMISSIONS
    assert Permission.GATEWAYS_UPDATE in GRANTABLE_PERMISSIONS
    assert Permission.GATEWAYS_ACTIVE_SET in GRANTABLE_PERMISSIONS
    assert Permission.GATEWAYS_REORDER in GRANTABLE_PERMISSIONS


def test_owner_has_gateways_permissions_by_default() -> None:
    assert PermissionPolicy.has_permission(OWNER, Permission.GATEWAYS_VIEW)
    assert PermissionPolicy.has_permission(OWNER, Permission.GATEWAYS_UPDATE)


def test_admin_does_not_have_gateways_permissions_by_default() -> None:
    assert not PermissionPolicy.has_permission(ADMIN, Permission.GATEWAYS_VIEW)
    assert not PermissionPolicy.has_permission(ADMIN, Permission.GATEWAYS_UPDATE)
    assert not PermissionPolicy.has_permission(ADMIN, Permission.GATEWAYS_ACTIVE_SET)
    assert not PermissionPolicy.has_permission(ADMIN, Permission.GATEWAYS_REORDER)


def test_admin_gains_gateways_view_via_grant() -> None:
    granted_admin = ADMIN.model_copy(update={"permission_grants": ["GATEWAYS_VIEW"]})
    assert PermissionPolicy.has_permission(granted_admin, Permission.GATEWAYS_VIEW)


def test_gateways_permissions_are_independently_gateable() -> None:
    view_only = OWNER.model_copy(
        update={
            "permission_revokes": [
                Permission.GATEWAYS_UPDATE.value,
                Permission.GATEWAYS_ACTIVE_SET.value,
                Permission.GATEWAYS_REORDER.value,
            ]
        }
    )
    assert PermissionPolicy.has_permission(view_only, Permission.GATEWAYS_VIEW)
    assert not PermissionPolicy.has_permission(view_only, Permission.GATEWAYS_UPDATE)


def test_plans_permissions_granted_to_admin_by_default() -> None:
    admin_default = ROLE_PERMISSIONS[Role.ADMIN]
    for permission in (
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
    ):
        assert permission in admin_default
        assert permission in PERMISSION_METADATA


def test_subscriptions_permissions_granted_to_admin_by_default() -> None:
    admin_default = ROLE_PERMISSIONS[Role.ADMIN]
    for permission in (
        Permission.SUBSCRIPTIONS_VIEW,
        Permission.SUBSCRIPTIONS_DETAIL_VIEW,
        Permission.SUBSCRIPTIONS_UPDATE,
        Permission.SUBSCRIPTIONS_SQUADS_MANAGE,
        Permission.SUBSCRIPTIONS_DELETE,
        Permission.ADDONS_VIEW,
        Permission.ADDONS_DETAIL_VIEW,
        Permission.ADDONS_CREATE,
        Permission.ADDONS_UPDATE,
        Permission.ADDONS_DELETE,
        Permission.ADDONS_PRICES_MANAGE,
        Permission.ADDONS_PRICE_OVERRIDE_MANAGE,
    ):
        assert permission in admin_default
        assert permission in PERMISSION_METADATA


def test_admin_role_has_all_referrals_permissions() -> None:
    admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.REFERRALS_VIEW in admin_perms
    assert Permission.REFERRALS_INVITED_VIEW in admin_perms
    assert Permission.REFERRALS_REVENUE_VIEW in admin_perms
    assert Permission.REFERRALS_LIST in admin_perms
    assert Permission.REFERRALS_SUMMARY_VIEW in admin_perms
    assert Permission.REFERRALS_SETTINGS_VIEW in admin_perms
    assert Permission.REFERRALS_SETTINGS_MANAGE in admin_perms
    assert Permission.REFERRALS_SETTINGS_RESET in admin_perms
    assert Permission.REFERRALS_POINTS_MANAGE in admin_perms
    assert Permission.REFERRALS_BONUS_DAYS_MANAGE in admin_perms
    assert Permission.REFERRALS_CODE_RESET in admin_perms


def test_backups_permissions_are_grantable_but_not_default_admin() -> None:
    backups_permissions = (
        Permission.BACKUPS_VIEW,
        Permission.BACKUPS_SETTINGS_VIEW,
        Permission.BACKUPS_SETTINGS_MANAGE,
        Permission.BACKUPS_RUN_VIEW,
        Permission.BACKUPS_RUN_CREATE,
        Permission.BACKUPS_RUN_DELETE,
        Permission.BACKUPS_RUN_CANCEL,
        Permission.BACKUPS_STATS_VIEW,
    )
    admin_default = ROLE_PERMISSIONS[Role.ADMIN]
    owner_default = ROLE_PERMISSIONS[Role.OWNER]
    for permission in backups_permissions:
        assert permission in GRANTABLE_PERMISSIONS
        assert permission not in admin_default
        assert permission in owner_default


def test_token_cannot_take_over_login_bot_or_payments() -> None:
    # still delegable to an admin, never to a bearer string in a script
    for permission in (
        Permission.OAUTH_SETTINGS_MANAGE,
        Permission.EMAIL_SETTINGS_MANAGE,
        Permission.BOT_SETTINGS_MANAGE,
        Permission.BOT_PROXY_SET,
        Permission.GATEWAYS_UPDATE,
        Permission.GATEWAYS_ACTIVE_SET,
        Permission.USERS_DELETE,
        Permission.BACKUPS_RUN_DELETE,
    ):
        assert permission in GRANTABLE_PERMISSIONS
        assert permission not in TOKEN_GRANTABLE_PERMISSIONS


def test_token_scope_wildcard_expands_to_every_token_grantable_permission() -> None:
    assert expand_token_scopes(["*"]) == set(TOKEN_GRANTABLE_PERMISSIONS)


def test_token_resource_scopes_follow_resource_and_kind() -> None:
    reads = expand_token_scopes(["users:read"])
    assert Permission.USERS_VIEW in reads
    assert Permission.USERS_BLOCK not in reads
    everything = expand_token_scopes(["users:*"])
    assert {Permission.USERS_VIEW, Permission.USERS_BLOCK} <= everything
    # excluded permissions never come back through a broader scope
    assert Permission.USERS_DELETE not in everything
    assert Permission.OAUTH_SETTINGS_MANAGE not in expand_token_scopes(["*"])


def test_token_leaf_scope_is_a_single_permission() -> None:
    assert expand_token_scopes(["PLANS_VIEW"]) == {Permission.PLANS_VIEW}
    assert expand_token_scopes(["USERS_DELETE", "bogus", "users:delete"]) == set()


def test_token_grantable_is_a_subset_of_grantable() -> None:
    assert TOKEN_GRANTABLE_PERMISSIONS < GRANTABLE_PERMISSIONS


def test_backup_download_is_owner_only() -> None:
    # a DATABASE dump holds every table, password hashes included, so it
    # subsumes every read permission and can't be delegated
    assert Permission.BACKUPS_RUN_DOWNLOAD not in GRANTABLE_PERMISSIONS
    assert Permission.BACKUPS_RUN_DOWNLOAD not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.BACKUPS_RUN_DOWNLOAD not in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.BACKUPS_RUN_DOWNLOAD in ROLE_PERMISSIONS[Role.OWNER]


def test_blacklist_permissions_are_owner_only_by_default() -> None:
    for perm in (
        Permission.BLACKLIST_VIEW,
        Permission.BLACKLIST_SOURCES_VIEW,
        Permission.BLACKLIST_ENTRY_ADD,
        Permission.BLACKLIST_ENTRY_REMOVE,
        Permission.BLACKLIST_SOURCE_ADD,
        Permission.BLACKLIST_SOURCE_REMOVE,
        Permission.BLACKLIST_SOURCE_UPDATE,
        Permission.BLACKLIST_SYNC,
        Permission.BLACKLIST_MATCHES_VIEW,
        Permission.USERS_BLOCK,
        Permission.USERS_UNBLOCK,
        Permission.USERS_UNBLOCK_BLACKLIST_MATCHES,
    ):
        assert perm in ROLE_PERMISSIONS[Role.OWNER]
        assert perm not in ROLE_PERMISSIONS[Role.ADMIN]


def test_unblock_blacklist_matches_is_not_grantable() -> None:
    assert Permission.USERS_UNBLOCK_BLACKLIST_MATCHES not in GRANTABLE_PERMISSIONS
    assert Permission.BLACKLIST_ENTRY_ADD in GRANTABLE_PERMISSIONS


def test_admin_role_has_ad_links_permissions() -> None:
    assert Permission.AD_LINKS_VIEW in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.AD_LINKS_CREATE in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.AD_LINKS_UPDATE in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.AD_LINKS_DELETE in ROLE_PERMISSIONS[Role.ADMIN]


def test_ad_links_permissions_are_grantable() -> None:
    assert Permission.AD_LINKS_VIEW in GRANTABLE_PERMISSIONS
    assert Permission.AD_LINKS_CREATE in GRANTABLE_PERMISSIONS


def test_admin_can_open_a_user_card_by_default() -> None:
    assert PermissionPolicy.has_permission(ADMIN, Permission.USERS_DETAIL_VIEW)


_TOKEN = SyntheticActor(
    id=0, role=Role.USER, name="API Token: ci", is_privileged=True, log="[api_token:ci]"
)


@pytest.mark.parametrize(
    ("actor", "target", "allowed"),
    [
        (ADMIN, REGULAR_USER, True),
        (ADMIN, ADMIN, False),
        (ADMIN, OWNER, False),
        (OWNER, REGULAR_USER, True),
        (OWNER, ADMIN, True),
        (OWNER, OWNER, False),
        (_TOKEN, REGULAR_USER, True),
        (_TOKEN, ADMIN, False),
        (_TOKEN, OWNER, False),
        (SYSTEM_ACTOR, ADMIN, True),
        (SYSTEM_ACTOR, OWNER, True),
    ],
)
def test_can_manage_reaches_customers_and_only_lower_staff(
    actor: Actor, target: UserDto, allowed: bool
) -> None:
    assert PermissionPolicy.can_manage(actor, target) is allowed


_ADMIN_SUBSCRIPTION_PERMISSIONS = (
    Permission.SUBSCRIPTIONS_GRANT,
    Permission.SUBSCRIPTIONS_PLAN_CHANGE,
    Permission.SUBSCRIPTIONS_STATUS_MANAGE,
    Permission.SUBSCRIPTIONS_TRAFFIC_RESET,
    Permission.SUBSCRIPTIONS_LINK_REISSUE,
    Permission.SUBSCRIPTIONS_DEVICES_VIEW,
    Permission.SUBSCRIPTIONS_DEVICES_DELETE,
    Permission.SUBSCRIPTIONS_DEVICES_DELETE_ALL,
)


def test_admin_subscription_permissions_are_admin_default_and_grantable() -> None:
    for permission in _ADMIN_SUBSCRIPTION_PERMISSIONS:
        assert permission in ROLE_PERMISSIONS[Role.ADMIN]
        assert permission in GRANTABLE_PERMISSIONS
        assert PERMISSION_METADATA[permission].resource == "subscriptions"


def test_irreversible_subscription_actions_are_not_token_grantable() -> None:
    assert Permission.SUBSCRIPTIONS_LINK_REISSUE not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.SUBSCRIPTIONS_DEVICES_DELETE not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.SUBSCRIPTIONS_DEVICES_DELETE_ALL not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.SUBSCRIPTIONS_DELETE_ALL not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.SUBSCRIPTIONS_GRANT in TOKEN_GRANTABLE_PERMISSIONS


def test_backups_write_token_cannot_rotate_or_reset_history() -> None:
    granted = expand_token_scopes(["backups:write"])
    assert Permission.BACKUPS_SETTINGS_RESET not in granted
    assert Permission.BACKUPS_RUN_CREATE not in granted


def test_oauth_settings_manage_is_owner_only_by_default() -> None:
    assert Permission.OAUTH_SETTINGS_MANAGE not in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.EMAIL_SETTINGS_MANAGE not in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.EMAIL_SETTINGS_MANAGE in ROLE_PERMISSIONS[Role.OWNER]
    assert Permission.EMAIL_SETTINGS_MANAGE in GRANTABLE_PERMISSIONS
    assert Permission.OAUTH_SETTINGS_MANAGE in ROLE_PERMISSIONS[Role.OWNER]
    assert Permission.OAUTH_SETTINGS_MANAGE in GRANTABLE_PERMISSIONS


@pytest.mark.parametrize(
    "permission", [Permission.TRANSACTIONS_REFUND, Permission.TRANSACTIONS_REFUND_PREVIEW]
)
def test_refund_permissions_are_owner_only_and_not_for_tokens(permission: Permission) -> None:
    assert permission in GRANTABLE_PERMISSIONS
    assert permission not in ROLE_PERMISSIONS[Role.ADMIN]
    assert permission in ROLE_PERMISSIONS[Role.OWNER]
    assert permission not in TOKEN_GRANTABLE_PERMISSIONS
