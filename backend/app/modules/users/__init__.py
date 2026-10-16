from app.modules.users.bot_blocked import mark_bot_blocked
from app.modules.users.di import get_users_providers
from app.modules.users.dto import (
    CreateUserDto,
    RegisterCabinetUserDto,
    RegisterTelegramUserDto,
    SetBotBlockedDto,
    SetMarketingOptOutDto,
    SetUserDiscountDto,
    UpdateUserDto,
    UserDto,
)
from app.modules.users.events import CabinetUserRegisteredEvent, TelegramUserRegisteredEvent
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserResponse
from app.modules.users.stats_repository import UserStatsRepository
from app.modules.users.unsubscribe import read_unsubscribe_token, unsubscribe_token
from app.modules.users.usecases import (
    AcceptRulesUseCase,
    BlockBlacklistMatchesUseCase,
    BlockUserUseCase,
    GetCurrentUserUseCase,
    RegisterCabinetUserUseCase,
    RegisterTelegramUserUseCase,
    SetBotBlockedUseCase,
    SetMarketingOptOutUseCase,
    SetUserDiscountUseCase,
    UnblockUserUseCase,
)
from app.modules.users.visibility import assert_manageable, get_visible_target, visible_user

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
    "SetBotBlockedDto",
    "SetBotBlockedUseCase",
    "SetMarketingOptOutDto",
    "SetMarketingOptOutUseCase",
    "SetUserDiscountDto",
    "SetUserDiscountUseCase",
    "TelegramUserRegisteredEvent",
    "UnblockUserUseCase",
    "UpdateUserDto",
    "UserDto",
    "UserRepository",
    "UserResponse",
    "UserStatsRepository",
    "assert_manageable",
    "get_users_providers",
    "get_visible_target",
    "mark_bot_blocked",
    "read_unsubscribe_token",
    "unsubscribe_token",
    "visible_user",
]
