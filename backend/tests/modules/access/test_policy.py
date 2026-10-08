from app.core.enums import AccessMode, Role
from app.modules.access import is_restricted_for
from app.modules.settings import AccessSettingsDto
from app.modules.users import UserDto


def test_restricted_mode_blocks_customers_only() -> None:
    settings = AccessSettingsDto(mode=AccessMode.RESTRICTED)

    assert is_restricted_for(UserDto(name="c", role=Role.USER), settings) is True
    assert is_restricted_for(UserDto(name="a", role=Role.ADMIN), settings) is False


def test_other_modes_never_restrict() -> None:
    for mode in (AccessMode.PUBLIC, AccessMode.INVITED):
        assert is_restricted_for(UserDto(name="c"), AccessSettingsDto(mode=mode)) is False
