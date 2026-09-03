from __future__ import annotations

from dataclasses import dataclass
from enum import auto
from typing import TYPE_CHECKING, Final, Literal

from app.core.enums import Role, UpperStrEnum
from app.core.exceptions import ValidationError

if TYPE_CHECKING:
    from app.modules.users.dto import UserDto


class Permission(UpperStrEnum):
    PUBLIC = auto()
    BOT_SETTINGS_VIEW = auto()
    BOT_COMMANDS_VIEW = auto()
    BOT_SETTINGS_MANAGE = auto()
    BOT_COMMANDS_MANAGE = auto()
    BOT_RESTART = auto()
    SHOP_SETTINGS_VIEW = auto()
    SHOP_SETTINGS_MANAGE = auto()
    OAUTH_SETTINGS_VIEW = auto()
    OAUTH_SETTINGS_MANAGE = auto()
    BANNERS_VIEW = auto()
    BANNERS_IMAGE_VIEW = auto()
    BANNERS_UPLOAD = auto()
    BANNERS_DELETE = auto()
    LOCALES_VIEW = auto()
    LOCALES_ADD = auto()
    LOCALES_REMOVE = auto()
    TRANSLATIONS_VIEW = auto()
    TRANSLATIONS_UPDATE = auto()
    TRANSLATIONS_RESET = auto()
    OWN_ACCOUNT_MANAGE = auto()
    ADMINS_MANAGE = auto()
    API_TOKENS_MANAGE = auto()
    EVENT_LOG_VIEW = auto()
    USERS_VIEW = auto()
    USERS_DELETE = auto()
    USERS_DISCOUNT_MANAGE = auto()
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
    GATEWAYS_TOGGLE = auto()
    GATEWAYS_REORDER = auto()
    PLANS_VIEW = auto()
    PLANS_CREATE = auto()
    PLANS_UPDATE = auto()
    PLANS_DELETE = auto()
    PLANS_DURATIONS_MANAGE = auto()
    PLANS_ACCESS_MANAGE = auto()
    PLANS_SQUADS_MANAGE = auto()
    PLANS_ORDER_MANAGE = auto()
    SUBSCRIPTIONS_VIEW = auto()
    SUBSCRIPTIONS_UPDATE = auto()
    SUBSCRIPTIONS_SQUADS_MANAGE = auto()
    SUBSCRIPTIONS_DELETE = auto()
    ADDONS_VIEW = auto()
    ADDONS_CREATE = auto()
    ADDONS_UPDATE = auto()
    ADDONS_DELETE = auto()
    ADDONS_PRICES_MANAGE = auto()
    ADDONS_REORDER = auto()
    PROMOCODES_VIEW = auto()
    PROMOCODES_CREATE = auto()
    PROMOCODES_UPDATE = auto()
    PROMOCODES_DELETE = auto()
    PROMOCODES_GENERATE_CODE = auto()
    PAYMENTS_VIEW = auto()
    PAYMENTS_ORDER_VIEW = auto()
    REFERRALS_VIEW = auto()
    REFERRALS_SETTINGS_VIEW = auto()
    REFERRALS_SETTINGS_MANAGE = auto()
    REFERRALS_POINTS_MANAGE = auto()


@dataclass(frozen=True, kw_only=True)
class PermissionMeta:
    resource: str
    kind: Literal["read", "write"]


PERMISSION_METADATA: Final[dict[Permission, PermissionMeta]] = {
    Permission.BOT_SETTINGS_VIEW: PermissionMeta(resource="bot_settings", kind="read"),
    Permission.BOT_COMMANDS_VIEW: PermissionMeta(resource="bot_settings", kind="read"),
    Permission.BOT_SETTINGS_MANAGE: PermissionMeta(resource="bot_settings", kind="write"),
    Permission.BOT_COMMANDS_MANAGE: PermissionMeta(resource="bot_settings", kind="write"),
    Permission.BOT_RESTART: PermissionMeta(resource="bot_settings", kind="write"),
    Permission.SHOP_SETTINGS_VIEW: PermissionMeta(resource="shop_settings", kind="read"),
    Permission.SHOP_SETTINGS_MANAGE: PermissionMeta(resource="shop_settings", kind="write"),
    Permission.OAUTH_SETTINGS_VIEW: PermissionMeta(resource="oauth_settings", kind="read"),
    Permission.OAUTH_SETTINGS_MANAGE: PermissionMeta(resource="oauth_settings", kind="write"),
    Permission.BANNERS_VIEW: PermissionMeta(resource="banners", kind="read"),
    Permission.BANNERS_IMAGE_VIEW: PermissionMeta(resource="banners", kind="read"),
    Permission.BANNERS_UPLOAD: PermissionMeta(resource="banners", kind="write"),
    Permission.BANNERS_DELETE: PermissionMeta(resource="banners", kind="write"),
    Permission.LOCALES_VIEW: PermissionMeta(resource="locales", kind="read"),
    Permission.LOCALES_ADD: PermissionMeta(resource="locales", kind="write"),
    Permission.LOCALES_REMOVE: PermissionMeta(resource="locales", kind="write"),
    Permission.TRANSLATIONS_VIEW: PermissionMeta(resource="translations", kind="read"),
    Permission.TRANSLATIONS_UPDATE: PermissionMeta(resource="translations", kind="write"),
    Permission.TRANSLATIONS_RESET: PermissionMeta(resource="translations", kind="write"),
    Permission.EVENT_LOG_VIEW: PermissionMeta(resource="event_log", kind="read"),
    Permission.USERS_VIEW: PermissionMeta(resource="users", kind="read"),
    Permission.USERS_DELETE: PermissionMeta(resource="users", kind="write"),
    Permission.USERS_DISCOUNT_MANAGE: PermissionMeta(resource="users", kind="write"),
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
    Permission.GATEWAYS_TOGGLE: PermissionMeta(resource="gateways", kind="write"),
    Permission.GATEWAYS_REORDER: PermissionMeta(resource="gateways", kind="write"),
    Permission.PLANS_VIEW: PermissionMeta(resource="plans", kind="read"),
    Permission.PLANS_CREATE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_UPDATE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_DELETE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_DURATIONS_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_ACCESS_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_SQUADS_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.PLANS_ORDER_MANAGE: PermissionMeta(resource="plans", kind="write"),
    Permission.SUBSCRIPTIONS_VIEW: PermissionMeta(resource="subscriptions", kind="read"),
    Permission.SUBSCRIPTIONS_UPDATE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_SQUADS_MANAGE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.SUBSCRIPTIONS_DELETE: PermissionMeta(resource="subscriptions", kind="write"),
    Permission.ADDONS_VIEW: PermissionMeta(resource="addons", kind="read"),
    Permission.ADDONS_CREATE: PermissionMeta(resource="addons", kind="write"),
    Permission.ADDONS_UPDATE: PermissionMeta(resource="addons", kind="write"),
    Permission.ADDONS_DELETE: PermissionMeta(resource="addons", kind="write"),
    Permission.ADDONS_PRICES_MANAGE: PermissionMeta(resource="addons", kind="write"),
    Permission.ADDONS_REORDER: PermissionMeta(resource="addons", kind="write"),
    Permission.PROMOCODES_VIEW: PermissionMeta(resource="promocodes", kind="read"),
    Permission.PROMOCODES_CREATE: PermissionMeta(resource="promocodes", kind="write"),
    Permission.PROMOCODES_UPDATE: PermissionMeta(resource="promocodes", kind="write"),
    Permission.PROMOCODES_DELETE: PermissionMeta(resource="promocodes", kind="write"),
    Permission.PROMOCODES_GENERATE_CODE: PermissionMeta(resource="promocodes", kind="write"),
    Permission.PAYMENTS_VIEW: PermissionMeta(resource="payments", kind="read"),
    Permission.PAYMENTS_ORDER_VIEW: PermissionMeta(resource="payments", kind="read"),
    Permission.REFERRALS_VIEW: PermissionMeta(resource="referrals", kind="read"),
    Permission.REFERRALS_SETTINGS_VIEW: PermissionMeta(resource="referrals", kind="read"),
    Permission.REFERRALS_SETTINGS_MANAGE: PermissionMeta(resource="referrals", kind="write"),
    Permission.REFERRALS_POINTS_MANAGE: PermissionMeta(resource="referrals", kind="write"),
}

GRANTABLE_PERMISSIONS: Final[frozenset[Permission]] = frozenset(PERMISSION_METADATA) | {
    Permission.OWN_ACCOUNT_MANAGE,
}

TOKEN_GRANTABLE_PERMISSIONS: Final[frozenset[Permission]] = frozenset(PERMISSION_METADATA)

ROLE_PERMISSIONS: Final[dict[Role, set[Permission]]] = {
    Role.SYSTEM: set(Permission),
    Role.OWNER: set(Permission),
    Role.ADMIN: {
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
        Permission.OWN_ACCOUNT_MANAGE,
        Permission.PLANS_VIEW,
        Permission.PLANS_CREATE,
        Permission.PLANS_UPDATE,
        Permission.PLANS_DELETE,
        Permission.PLANS_DURATIONS_MANAGE,
        Permission.PLANS_ACCESS_MANAGE,
        Permission.PLANS_SQUADS_MANAGE,
        Permission.PLANS_ORDER_MANAGE,
        Permission.SUBSCRIPTIONS_VIEW,
        Permission.SUBSCRIPTIONS_UPDATE,
        Permission.SUBSCRIPTIONS_SQUADS_MANAGE,
        Permission.SUBSCRIPTIONS_DELETE,
        Permission.ADDONS_VIEW,
        Permission.ADDONS_CREATE,
        Permission.ADDONS_UPDATE,
        Permission.ADDONS_DELETE,
        Permission.ADDONS_PRICES_MANAGE,
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
    },
    Role.USER: set(),
}


def assert_grantable(
    permissions: list[Permission], allowed: frozenset[Permission] = GRANTABLE_PERMISSIONS
) -> None:
    non_grantable = set(permissions) - allowed
    if non_grantable:
        names = ", ".join(sorted(p.value for p in non_grantable))
        raise ValidationError(f"Not grantable via permission overrides: {names}")


class PermissionPolicy:
    @staticmethod
    def effective_permissions(actor: UserDto) -> set[Permission]:
        if actor.role == Role.SYSTEM:
            return set(Permission)

        base = ROLE_PERMISSIONS.get(actor.role, set())
        grants = {Permission(p) for p in (actor.permission_grants or []) if p in Permission}
        revokes = {Permission(p) for p in (actor.permission_revokes or []) if p in Permission}
        return (base | grants) - revokes

    @staticmethod
    def has_permission(actor: UserDto, permission: "Permission") -> bool:
        if permission is Permission.PUBLIC:
            return True
        return permission in PermissionPolicy.effective_permissions(actor)
