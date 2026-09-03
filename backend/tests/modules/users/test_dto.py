from app.core.enums import Locale, Role
from app.modules.users.dto import UserDto


def test_regular_role_is_not_privileged_by_default() -> None:
    user = UserDto(id=1, name="Bob", role=Role.USER, language=Locale.EN)
    assert not user.is_privileged


def test_admin_role_is_privileged() -> None:
    admin = UserDto(id=1, name="Admin", role=Role.ADMIN, language=Locale.EN)
    assert admin.is_privileged
