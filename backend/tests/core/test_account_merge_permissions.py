from app.core.enums import Role
from app.core.security.permissions import (
    GRANTABLE_PERMISSIONS,
    ROLE_PERMISSIONS,
    TOKEN_GRANTABLE_PERMISSIONS,
    Permission,
)


def test_merge_and_bind_are_owner_default_grantable_not_token() -> None:
    for permission in (Permission.USERS_MERGE, Permission.USERS_TELEGRAM_BIND):
        assert permission in ROLE_PERMISSIONS[Role.OWNER]
        assert permission not in ROLE_PERMISSIONS[Role.ADMIN]
        assert permission in GRANTABLE_PERMISSIONS
        assert permission not in TOKEN_GRANTABLE_PERMISSIONS


def test_merge_preview_is_owner_default_grantable_not_token() -> None:
    permission = Permission.USERS_MERGE_PREVIEW
    assert permission in ROLE_PERMISSIONS[Role.OWNER]
    assert permission not in ROLE_PERMISSIONS[Role.ADMIN]
    assert permission in GRANTABLE_PERMISSIONS
    assert permission not in TOKEN_GRANTABLE_PERMISSIONS
