from app.modules.users.di import get_users_providers
from app.modules.users.dto import (
    CreateUserDto,
    RegisterTelegramUserDto,
    SetUserDiscountDto,
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
    SetUserDiscountUseCase,
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
    "SetUserDiscountDto",
    "SetUserDiscountUseCase",
    "TelegramUserRegisteredEvent",
    "UnblockAllUsersUseCase",
    "UnblockUserUseCase",
    "UpdateUserDto",
    "UserDto",
    "UserRepository",
    "UserStatsRepository",
    "get_users_providers",
]
