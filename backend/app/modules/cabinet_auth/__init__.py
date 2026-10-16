from app.modules.cabinet_auth.api.schemas import (
    BotSignInRequest,
    DeeplinkResponse,
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
)
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.di import get_cabinet_auth_providers
from app.modules.cabinet_auth.dto import (
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
    record_failure,
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
    "BotSignInRequest",
    "CabinetMethodsDto",
    "CabinetNewDeviceSignInEvent",
    "CabinetOAuthAuthorizeUseCase",
    "CabinetOAuthCallbackUseCase",
    "CabinetSignIn",
    "CabinetSignedInEvent",
    "DeeplinkResponse",
    "DeeplinkStore",
    "DeeplinkTicketDto",
    "EmailCodeAttemptsExhausted",
    "EmailCodeAttemptsExhaustedEvent",
    "EmailCodeExpired",
    "EmailCodeStore",
    "GetCabinetMethodsUseCase",
    "InviteCodesDto",
    "IssueBotSignInLinkUseCase",
    "OAuthAuthorizeResponse",
    "OAuthCallbackRequest",
    "RequestDeeplinkUseCase",
    "TelegramProfileDto",
    "email_key",
    "fail_budget_exhausted",
    "get_cabinet_auth_providers",
    "is_allowed_domain",
    "record_failure",
    "send_limit_hit",
    "telegram_profile_from_oauth",
]
