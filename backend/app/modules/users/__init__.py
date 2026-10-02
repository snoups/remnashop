from app.modules.users.di import get_users_providers
from app.modules.users.dto import (
    CreateUserDto,
    RegisterTelegramUserDto,
    SetUserPersonalDiscountDto,
    UpdateUserDto,
    UserDto,
)
from app.modules.users.events import TelegramUserRegisteredEvent
from app.modules.users.repository import UserRepository
from app.modules.users.stats_repository import UserStatsRepository
from app.modules.users.usecases import (
    BlockBlacklistMatchesUseCase,
    BlockUserUseCase,
    GetCurrentUserUseCase,
    RegisterTelegramUserUseCase,
    SetUserPersonalDiscountUseCase,
    UnblockAllUsersUseCase,
    UnblockUserUseCase,
)

__all__ = [
    "BlockBlacklistMatchesUseCase",
    "BlockUserUseCase",
    "CreateUserDto",
    "GetCurrentUserUseCase",
    "RegisterTelegramUserDto",
    "RegisterTelegramUserUseCase",
    "SetUserPersonalDiscountDto",
    "SetUserPersonalDiscountUseCase",
    "TelegramUserRegisteredEvent",
    "UnblockAllUsersUseCase",
    "UnblockUserUseCase",
    "UpdateUserDto",
    "UserDto",
    "UserRepository",
    "UserStatsRepository",
    "get_users_providers",
]
