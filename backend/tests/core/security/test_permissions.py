import pytest

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


def test_admin_does_not_have_view_users_by_default() -> None:
    assert not PermissionPolicy.has_permission(ADMIN, Permission.USERS_VIEW)


def test_admin_gains_view_users_via_grant() -> None:
    granted_admin = ADMIN.model_copy(update={"permission_grants": ["USERS_VIEW"]})
    assert PermissionPolicy.has_permission(granted_admin, Permission.USERS_VIEW)


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


def test_manage_own_account_is_not_token_grantable() -> None:
    assert Permission.OWN_ACCOUNT_MANAGE not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.OWN_ACCOUNT_MANAGE in GRANTABLE_PERMISSIONS  # still grantable to real admins


def test_every_catalog_permission_has_metadata() -> None:
    non_catalog = {
        Permission.PUBLIC,
        Permission.OWN_ACCOUNT_MANAGE,
        Permission.ADMINS_MANAGE,
        Permission.API_TOKENS_MANAGE,
        Permission.PRICING_RATES_MANAGE,
        Permission.PRICING_ANCHOR_MANAGE,
        Permission.USERS_UNBLOCK_ALL,
    }
    assert set(Permission) - PERMISSION_METADATA.keys() == non_catalog


def test_role_permissions_admin_matches_expected_defaults() -> None:
    assert ROLE_PERMISSIONS[Role.ADMIN] == {
        Permission.BOT_SETTINGS_VIEW,
        Permission.BOT_COMMANDS_VIEW,
        Permission.BOT_SETTINGS_MANAGE,
        Permission.BOT_COMMANDS_MANAGE,
        Permission.BOT_RESTART,
        Permission.SHOP_SETTINGS_VIEW,
        Permission.SHOP_SETTINGS_MANAGE,
        Permission.BANNERS_VIEW,
        Permission.BANNERS_IMAGE_VIEW,
        Permission.BANNERS_UPLOAD,
        Permission.BANNERS_DELETE,
        Permission.OAUTH_SETTINGS_VIEW,
        Permission.OAUTH_SETTINGS_MANAGE,
        Permission.LOCALES_VIEW,
        Permission.LOCALES_ADD,
        Permission.LOCALES_REMOVE,
        Permission.TRANSLATIONS_VIEW,
        Permission.TRANSLATIONS_UPDATE,
        Permission.TRANSLATIONS_RESET,
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
        Permission.PLANS_CREATE,
        Permission.PLANS_UPDATE,
        Permission.PLANS_DELETE,
        Permission.PLANS_DURATIONS_MANAGE,
        Permission.PLANS_PRICE_OVERRIDE_MANAGE,
        Permission.PLANS_DURATION_BASE_PRICE_MANAGE,
        Permission.PLANS_ACCESS_MANAGE,
        Permission.PLANS_SQUADS_MANAGE,
        Permission.PLANS_ORDER_MANAGE,
        Permission.PRICING_VIEW,
        Permission.PRICING_PREVIEW_VIEW,
        Permission.PRICING_SETTINGS_MANAGE,
        Permission.PRICING_BASE_ADJUST_MANAGE,
        Permission.SUBSCRIPTIONS_VIEW,
        Permission.SUBSCRIPTIONS_UPDATE,
        Permission.SUBSCRIPTIONS_SQUADS_MANAGE,
        Permission.SUBSCRIPTIONS_DELETE,
        Permission.ADDONS_VIEW,
        Permission.ADDONS_CREATE,
        Permission.ADDONS_UPDATE,
        Permission.ADDONS_DELETE,
        Permission.ADDONS_PRICES_MANAGE,
        Permission.ADDONS_PRICE_OVERRIDE_MANAGE,
        Permission.ADDONS_REORDER,
        Permission.PROMOCODES_VIEW,
        Permission.PROMOCODES_CREATE,
        Permission.PROMOCODES_UPDATE,
        Permission.PROMOCODES_DELETE,
        Permission.PROMOCODES_GENERATE_CODE,
        Permission.USERS_DISCOUNT_MANAGE,
        Permission.PAYMENTS_VIEW,
        Permission.PAYMENTS_ORDER_VIEW,
        Permission.REFERRALS_VIEW,
        Permission.REFERRALS_SETTINGS_VIEW,
        Permission.REFERRALS_SETTINGS_MANAGE,
        Permission.REFERRALS_POINTS_MANAGE,
        Permission.AD_LINKS_VIEW,
        Permission.AD_LINKS_STATS_VIEW,
        Permission.AD_LINKS_USERS_VIEW,
        Permission.AD_LINKS_CREATE,
        Permission.AD_LINKS_GENERATE_CODE,
        Permission.AD_LINKS_UPDATE,
        Permission.AD_LINKS_DELETE,
        Permission.ANALYTICS_VIEW,
        Permission.ANALYTICS_FUNNEL_VIEW,
        Permission.ANALYTICS_COHORTS_VIEW,
        Permission.ANALYTICS_LTV_VIEW,
    }


def test_user_sessions_revoke_is_distinct_from_view() -> None:
    assert Permission.USER_SESSIONS_REVOKE != Permission.USER_SESSIONS_VIEW
    granted_view_only = ADMIN.model_copy(
        update={"permission_grants": [Permission.USER_SESSIONS_VIEW.value]}
    )
    assert not PermissionPolicy.has_permission(granted_view_only, Permission.USER_SESSIONS_REVOKE)


def test_banner_permissions_are_independently_gateable() -> None:
    # ADMIN's role default includes all four banner permissions -- revoke
    # three to isolate BANNERS_UPLOAD as the only one true.
    upload_only = ADMIN.model_copy(
        update={
            "permission_revokes": [
                Permission.BANNERS_VIEW.value,
                Permission.BANNERS_IMAGE_VIEW.value,
                Permission.BANNERS_DELETE.value,
            ]
        }
    )
    assert PermissionPolicy.has_permission(upload_only, Permission.BANNERS_UPLOAD)
    assert not PermissionPolicy.has_permission(upload_only, Permission.BANNERS_DELETE)
    assert not PermissionPolicy.has_permission(upload_only, Permission.BANNERS_VIEW)
    assert not PermissionPolicy.has_permission(upload_only, Permission.BANNERS_IMAGE_VIEW)


def test_gateways_permissions_are_grantable() -> None:
    assert Permission.GATEWAYS_VIEW in GRANTABLE_PERMISSIONS
    assert Permission.GATEWAYS_UPDATE in GRANTABLE_PERMISSIONS
    assert Permission.GATEWAYS_TOGGLE in GRANTABLE_PERMISSIONS
    assert Permission.GATEWAYS_REORDER in GRANTABLE_PERMISSIONS


def test_owner_has_gateways_permissions_by_default() -> None:
    assert PermissionPolicy.has_permission(OWNER, Permission.GATEWAYS_VIEW)
    assert PermissionPolicy.has_permission(OWNER, Permission.GATEWAYS_UPDATE)


def test_admin_does_not_have_gateways_permissions_by_default() -> None:
    assert not PermissionPolicy.has_permission(ADMIN, Permission.GATEWAYS_VIEW)
    assert not PermissionPolicy.has_permission(ADMIN, Permission.GATEWAYS_UPDATE)
    assert not PermissionPolicy.has_permission(ADMIN, Permission.GATEWAYS_TOGGLE)
    assert not PermissionPolicy.has_permission(ADMIN, Permission.GATEWAYS_REORDER)


def test_admin_gains_gateways_view_via_grant() -> None:
    granted_admin = ADMIN.model_copy(update={"permission_grants": ["GATEWAYS_VIEW"]})
    assert PermissionPolicy.has_permission(granted_admin, Permission.GATEWAYS_VIEW)


def test_gateways_permissions_are_independently_gateable() -> None:
    view_only = OWNER.model_copy(
        update={
            "permission_revokes": [
                Permission.GATEWAYS_UPDATE.value,
                Permission.GATEWAYS_TOGGLE.value,
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
        Permission.PLANS_CREATE,
        Permission.PLANS_UPDATE,
        Permission.PLANS_DELETE,
        Permission.PLANS_DURATIONS_MANAGE,
        Permission.PLANS_PRICE_OVERRIDE_MANAGE,
        Permission.PLANS_DURATION_BASE_PRICE_MANAGE,
        Permission.PLANS_ACCESS_MANAGE,
        Permission.PLANS_SQUADS_MANAGE,
        Permission.PLANS_ORDER_MANAGE,
    ):
        assert permission in admin_default
        assert permission in PERMISSION_METADATA


def test_subscriptions_permissions_granted_to_admin_by_default() -> None:
    admin_default = ROLE_PERMISSIONS[Role.ADMIN]
    for permission in (
        Permission.SUBSCRIPTIONS_VIEW,
        Permission.SUBSCRIPTIONS_UPDATE,
        Permission.SUBSCRIPTIONS_SQUADS_MANAGE,
        Permission.SUBSCRIPTIONS_DELETE,
        Permission.ADDONS_VIEW,
        Permission.ADDONS_CREATE,
        Permission.ADDONS_UPDATE,
        Permission.ADDONS_DELETE,
        Permission.ADDONS_PRICES_MANAGE,
        Permission.ADDONS_PRICE_OVERRIDE_MANAGE,
        Permission.ADDONS_REORDER,
    ):
        assert permission in admin_default
        assert permission in PERMISSION_METADATA


def test_admin_role_has_all_referrals_permissions() -> None:
    admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.REFERRALS_VIEW in admin_perms
    assert Permission.REFERRALS_SETTINGS_VIEW in admin_perms
    assert Permission.REFERRALS_SETTINGS_MANAGE in admin_perms
    assert Permission.REFERRALS_POINTS_MANAGE in admin_perms


def test_backups_permissions_are_grantable_but_not_default_admin() -> None:
    backups_permissions = (
        Permission.BACKUPS_VIEW,
        Permission.BACKUPS_SETTINGS_VIEW,
        Permission.BACKUPS_SETTINGS_MANAGE,
        Permission.BACKUPS_RUN_VIEW,
        Permission.BACKUPS_RUN_CREATE,
        Permission.BACKUPS_RUN_DOWNLOAD,
        Permission.BACKUPS_RUN_DELETE,
    )
    admin_default = ROLE_PERMISSIONS[Role.ADMIN]
    owner_default = ROLE_PERMISSIONS[Role.OWNER]
    for permission in backups_permissions:
        assert permission in GRANTABLE_PERMISSIONS
        assert permission not in admin_default
        assert permission in owner_default


def test_blacklist_permissions_are_owner_only_by_default() -> None:
    for perm in (
        Permission.BLACKLIST_VIEW,
        Permission.BLACKLIST_SOURCES_VIEW,
        Permission.BLACKLIST_ENTRY_ADD,
        Permission.BLACKLIST_ENTRY_REMOVE,
        Permission.BLACKLIST_SOURCE_ADD,
        Permission.BLACKLIST_SOURCE_REMOVE,
        Permission.BLACKLIST_SOURCE_TOGGLE,
        Permission.BLACKLIST_SYNC,
        Permission.USERS_BLOCK,
        Permission.USERS_UNBLOCK,
        Permission.USERS_BULK_BLOCK,
        Permission.USERS_UNBLOCK_ALL,
    ):
        assert perm in ROLE_PERMISSIONS[Role.OWNER]
        assert perm not in ROLE_PERMISSIONS[Role.ADMIN]


def test_unblock_all_is_not_grantable() -> None:
    assert Permission.USERS_UNBLOCK_ALL not in GRANTABLE_PERMISSIONS
    assert Permission.BLACKLIST_ENTRY_ADD in GRANTABLE_PERMISSIONS


def test_admin_role_has_ad_links_permissions() -> None:
    assert Permission.AD_LINKS_VIEW in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.AD_LINKS_CREATE in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.AD_LINKS_UPDATE in ROLE_PERMISSIONS[Role.ADMIN]
    assert Permission.AD_LINKS_DELETE in ROLE_PERMISSIONS[Role.ADMIN]


def test_ad_links_permissions_are_grantable() -> None:
    assert Permission.AD_LINKS_VIEW in GRANTABLE_PERMISSIONS
    assert Permission.AD_LINKS_CREATE in GRANTABLE_PERMISSIONS
