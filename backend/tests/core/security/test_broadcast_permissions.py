from app.core.enums import Role
from app.core.security.permissions import (
    GRANTABLE_PERMISSIONS,
    ROLE_PERMISSIONS,
    TOKEN_GRANTABLE_PERMISSIONS,
    Permission,
)

_ALL = {
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
}


def test_admin_has_every_broadcast_permission() -> None:
    assert _ALL <= ROLE_PERMISSIONS[Role.ADMIN]
    assert _ALL <= GRANTABLE_PERMISSIONS


def test_tokens_cannot_send_recall_retry_or_delete() -> None:
    assert Permission.BROADCASTS_SEND not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.BROADCASTS_RECALL not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.BROADCASTS_RETRY not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.BROADCASTS_CANCEL in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.BROADCASTS_TEST_SEND in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.BROADCASTS_DELETE not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.BROADCASTS_CREATE in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.BROADCASTS_SUMMARY_VIEW in TOKEN_GRANTABLE_PERMISSIONS
