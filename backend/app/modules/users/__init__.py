from app.modules.users.bot_blocked import mark_bot_blocked
from app.modules.users.di import get_users_providers
from app.modules.users.dto import (
    CreateUserDto,
    RegisterCabinetUserDto,
    RegisterTelegramUserDto,
    RegistrationSnapshotDto,
    SetBotBlockedDto,
    SetMarketingOptOutDto,
    SetUserDiscountDto,
    UpdateUserDto,
    UserDto,
)
from app.modules.users.events import CabinetUserRegisteredEvent, TelegramUserRegisteredEvent
from app.modules.users.ports import PasskeyRevoker, SessionRevoker, SubscriptionRevoker
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    CurrentUserResponse,
    UserResponse,
    to_current_user_response,
)
from app.modules.users.stats_repository import UserStatsRepository
from app.modules.users.unsubscribe import read_unsubscribe_token, unsubscribe_token
from app.modules.users.usecases import (
    AcceptRulesUseCase,
    BlockBlacklistMatchesUseCase,
    BlockUserUseCase,
    FindTelegramUserUseCase,
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
    "CurrentUserResponse",
    "FindTelegramUserUseCase",
    "GetCurrentUserUseCase",
    "PasskeyRevoker",
    "RegisterCabinetUserDto",
    "RegisterCabinetUserUseCase",
    "RegisterTelegramUserDto",
    "RegisterTelegramUserUseCase",
    "RegistrationSnapshotDto",
    "SessionRevoker",
    "SetBotBlockedDto",
    "SetBotBlockedUseCase",
    "SetMarketingOptOutDto",
    "SetMarketingOptOutUseCase",
    "SetUserDiscountDto",
    "SetUserDiscountUseCase",
    "SubscriptionRevoker",
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
    "to_current_user_response",
    "unsubscribe_token",
    "visible_user",
]
