from app.modules.cabinet_auth.attempts import (
    BOT_SIGNIN_FAILURES,
    EMAIL_VERIFY_FAILURES,
    OAUTH_CALLBACK_FAILURES,
)
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.di import get_cabinet_auth_providers
from app.modules.cabinet_auth.dto import (
    BotSignInLinkDto,
    CabinetMethodsDto,
    DeeplinkTicketDto,
    InviteCodesDto,
    TelegramProfileDto,
)
from app.modules.cabinet_auth.email_codes import (
    EmailCodeAttemptsExhausted,
    EmailCodeExpired,
    EmailCodeStore,
    email_key,
    fail_budget_exhausted,
    release_attempt,
    reserve_attempt,
    send_limit_hit,
)
from app.modules.cabinet_auth.email_domains import is_allowed_domain
from app.modules.cabinet_auth.events import (
    CabinetNewDeviceSignInEvent,
    CabinetSignedInEvent,
    EmailCodeAttemptsExhaustedEvent,
)
from app.modules.cabinet_auth.sign_in import CabinetSignIn, telegram_profile_from_oauth
from app.modules.cabinet_auth.usecases import (
    CabinetOAuthAuthorizeUseCase,
    CabinetOAuthCallbackUseCase,
    GetCabinetMethodsUseCase,
    IssueBotSignInLinkUseCase,
    RequestDeeplinkUseCase,
)

__all__ = [
    "BOT_SIGNIN_FAILURES",
    "EMAIL_VERIFY_FAILURES",
    "OAUTH_CALLBACK_FAILURES",
    "BotSignInLinkDto",
    "CabinetMethodsDto",
    "CabinetNewDeviceSignInEvent",
    "CabinetOAuthAuthorizeUseCase",
    "CabinetOAuthCallbackUseCase",
    "CabinetSignIn",
    "CabinetSignedInEvent",
    "DeeplinkStore",
    "DeeplinkTicketDto",
    "EmailCodeAttemptsExhausted",
    "EmailCodeAttemptsExhaustedEvent",
    "EmailCodeExpired",
    "EmailCodeStore",
    "GetCabinetMethodsUseCase",
    "InviteCodesDto",
    "IssueBotSignInLinkUseCase",
    "RequestDeeplinkUseCase",
    "TelegramProfileDto",
    "email_key",
    "fail_budget_exhausted",
    "get_cabinet_auth_providers",
    "is_allowed_domain",
    "release_attempt",
    "reserve_attempt",
    "send_limit_hit",
    "telegram_profile_from_oauth",
]
