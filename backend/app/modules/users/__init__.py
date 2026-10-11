from app.modules.users.di import get_users_providers
from app.modules.users.dto import (
    CreateUserDto,
    RegisterCabinetUserDto,
    RegisterTelegramUserDto,
    SetUserDiscountDto,
    UpdateUserDto,
    UserDto,
)
from app.modules.users.events import CabinetUserRegisteredEvent, TelegramUserRegisteredEvent
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserResponse
from app.modules.users.stats_repository import UserStatsRepository
from app.modules.users.usecases import (
    AcceptRulesUseCase,
    BlockBlacklistMatchesUseCase,
    BlockUserUseCase,
    GetCurrentUserUseCase,
    RegisterCabinetUserUseCase,
    RegisterTelegramUserUseCase,
    SetMarketingOptOutUseCase,
    SetUserDiscountUseCase,
    UnblockAllUsersUseCase,
    UnblockUserUseCase,
)
from app.modules.users.visibility import visible_user

__all__ = [
    "AcceptRulesUseCase",
    "BlockBlacklistMatchesUseCase",
    "BlockUserUseCase",
    "CabinetUserRegisteredEvent",
    "CreateUserDto",
    "GetCurrentUserUseCase",
    "RegisterCabinetUserDto",
    "RegisterCabinetUserUseCase",
    "RegisterTelegramUserDto",
    "RegisterTelegramUserUseCase",
    "SetMarketingOptOutUseCase",
    "SetUserDiscountDto",
    "SetUserDiscountUseCase",
    "TelegramUserRegisteredEvent",
    "UnblockAllUsersUseCase",
    "UnblockUserUseCase",
    "UpdateUserDto",
    "UserDto",
    "UserRepository",
    "UserResponse",
    "UserStatsRepository",
    "get_users_providers",
    "visible_user",
]
