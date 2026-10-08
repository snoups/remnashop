from app.core.enums import AccessMode
from app.modules.settings import AccessSettingsDto
from app.modules.users import UserDto


def is_restricted_for(user: UserDto, settings: AccessSettingsDto) -> bool:
    return settings.mode is AccessMode.RESTRICTED and not user.is_privileged
