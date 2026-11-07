from app.modules.users.bot_blocked import mark_bot_blocked
from app.modules.users.di import get_users_providers
from app.modules.users.display_name import clean_display_name
from app.modules.users.dto import (
    CreateUserDto,
    RegisterCabinetUserDto,
    RegisterTelegramUserDto,
    RegistrationSnapshotDto,
    SetBotBlockedDto,
    SetMarketingOptOutDto,
    UpdateUserDto,
    UserDto,
    UserListItemDto,
)
from app.modules.users.events import (
    CabinetUserRegisteredEvent,
    TelegramUserRegisteredEvent,
    UserDeletedEvent,
)
from app.modules.users.listing import detail_roles
from app.modules.users.ports import (
    OAuthIdentityLookup,
    PasskeyRevoker,
    PromocodeLiveness,
    SessionRevoker,
    SignInMethodCheck,
    SubscriptionRevoker,
)
from app.modules.users.repository import UserRepository, generate_referral_code
from app.modules.users.schemas import (
    CurrentUserResponse,
    UserListItemResponse,
    UserResponse,
    to_current_user_response,
)
from app.modules.users.stats_repository import UserStatsRepository
from app.modules.users.unsubscribe import unsubscribe_token
from app.modules.users.usecases import (
    FindTelegramUserUseCase,
    RegisterCabinetUserUseCase,
    RegisterTelegramUserUseCase,
    SetBotBlockedUseCase,
    SetMarketingOptOutUseCase,
)
from app.modules.users.visibility import (
    assert_manageable,
    assert_own_or_manageable,
    get_visible_target,
    visible_user,
)

__all__ = [
    "CabinetUserRegisteredEvent",
    "CreateUserDto",
    "CurrentUserResponse",
    "FindTelegramUserUseCase",
    "OAuthIdentityLookup",
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
    "SignInMethodCheck",
    "SubscriptionRevoker",
    "TelegramUserRegisteredEvent",
    "UpdateUserDto",
    "UserDeletedEvent",
    "UserDto",
    "UserListItemDto",
    "UserListItemResponse",
    "UserRepository",
    "UserResponse",
    "UserStatsRepository",
    "assert_manageable",
    "assert_own_or_manageable",
    "clean_display_name",
    "detail_roles",
    "generate_referral_code",
    "get_users_providers",
    "get_visible_target",
    "mark_bot_blocked",
    "to_current_user_response",
    "unsubscribe_token",
    "visible_user",
]
