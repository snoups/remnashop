from app.modules.users.bot_blocked import mark_bot_blocked
from app.modules.users.di import get_users_providers
from app.modules.users.dto import (
    CreateUserDto,
    RegisterCabinetUserDto,
    RegisterTelegramUserDto,
    RegistrationSnapshotDto,
    SetBotBlockedDto,
    SetMarketingOptOutDto,
    UpdateUserDto,
    UserDto,
)
from app.modules.users.events import (
    CabinetUserRegisteredEvent,
    TelegramUserRegisteredEvent,
    UserDeletedEvent,
)
from app.modules.users.ports import (
    PasskeyRevoker,
    PromocodeLiveness,
    SessionRevoker,
    SubscriptionRevoker,
)
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import CurrentUserResponse, UserResponse, to_current_user_response
from app.modules.users.stats_repository import UserStatsRepository
from app.modules.users.unsubscribe import unsubscribe_token
from app.modules.users.usecases import (
    FindTelegramUserUseCase,
    RegisterCabinetUserUseCase,
    RegisterTelegramUserUseCase,
    SetBotBlockedUseCase,
    SetMarketingOptOutUseCase,
)
from app.modules.users.visibility import assert_manageable, get_visible_target, visible_user

__all__ = [
    "CabinetUserRegisteredEvent",
    "CreateUserDto",
    "CurrentUserResponse",
    "FindTelegramUserUseCase",
    "PasskeyRevoker",
    "PromocodeLiveness",
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
    "SubscriptionRevoker",
    "TelegramUserRegisteredEvent",
    "UpdateUserDto",
    "UserDeletedEvent",
    "UserDto",
    "UserRepository",
    "UserResponse",
    "UserStatsRepository",
    "assert_manageable",
    "get_users_providers",
    "get_visible_target",
    "mark_bot_blocked",
    "to_current_user_response",
    "unsubscribe_token",
    "visible_user",
]
