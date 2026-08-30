from app.core.enums import Locale, Role
from app.modules.users.dto import UserDto


def test_regular_role_is_not_privileged_by_default() -> None:
    user = UserDto(id=1, name="Bob", role=Role.USER, language=Locale.EN)
    assert not user.is_privileged


def test_admin_role_is_privileged() -> None:
    admin = UserDto(id=1, name="Admin", role=Role.ADMIN, language=Locale.EN)
    assert admin.is_privileged


def test_api_token_actor_is_privileged_despite_user_role() -> None:
    token_actor = UserDto(
        id=0, name="API Token: ci", role=Role.USER, language=Locale.EN, is_api_token=True
    )
    assert token_actor.is_privileged
