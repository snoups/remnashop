from app.core.enums import Locale, Role
from app.modules.users.dto import UserDto
from app.modules.users.visibility import visible_user

ADMIN_ACTOR = UserDto(id=1, name="admin", role=Role.ADMIN, language=Locale.EN)
OWNER_ACTOR = UserDto(id=2, name="owner", role=Role.OWNER, language=Locale.EN)


def _user(role: Role) -> UserDto:
    return UserDto(id=3, name="subject", role=role, language=Locale.EN)


def test_staff_hidden_without_admins_manage() -> None:
    assert visible_user(ADMIN_ACTOR, _user(Role.OWNER)) is None


def test_staff_visible_with_admins_manage() -> None:
    owner = _user(Role.OWNER)
    assert visible_user(OWNER_ACTOR, owner) is owner


def test_customer_always_visible() -> None:
    customer = _user(Role.USER)
    assert visible_user(ADMIN_ACTOR, customer) is customer


def test_missing_user_stays_missing() -> None:
    assert visible_user(ADMIN_ACTOR, None) is None


def test_caller_sees_their_own_staff_row() -> None:
    assert visible_user(ADMIN_ACTOR, ADMIN_ACTOR) is ADMIN_ACTOR
