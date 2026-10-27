from app.modules.cabinet_auth.attempts import (
    BOT_SIGNIN_FAILURES,
    EMAIL_VERIFY_FAILURES,
    OAUTH_CALLBACK_FAILURES,
)
from app.modules.cabinet_auth.deeplink_store import DeeplinkStore
from app.modules.cabinet_auth.di import get_cabinet_auth_providers
from app.modules.cabinet_auth.dto import DeeplinkTicketDto, InviteCodesDto, TelegramProfileDto
from app.modules.cabinet_auth.email_codes import (
    EmailCodeStore,
    email_key,
    fail_budget_exhausted,
    require_email_sign_in,
    send_limit_hit,
    verify_email_code,
)
from app.modules.cabinet_auth.email_domains import is_allowed_domain
from app.modules.cabinet_auth.events import (
    CabinetNewDeviceSignInEvent,
)
from app.modules.cabinet_auth.sign_in import telegram_profile_from_oauth
from app.modules.cabinet_auth.usecases import (
    CabinetOAuthAuthorizeUseCase,
    CabinetOAuthCallbackUseCase,
    IssueBotSignInLinkUseCase,
    RequestDeeplinkUseCase,
)

__all__ = [
    "BOT_SIGNIN_FAILURES",
    "EMAIL_VERIFY_FAILURES",
    "OAUTH_CALLBACK_FAILURES",
    "CabinetNewDeviceSignInEvent",
    "CabinetOAuthAuthorizeUseCase",
    "CabinetOAuthCallbackUseCase",
    "DeeplinkStore",
    "DeeplinkTicketDto",
    "EmailCodeStore",
    "InviteCodesDto",
    "IssueBotSignInLinkUseCase",
    "RequestDeeplinkUseCase",
    "TelegramProfileDto",
    "email_key",
    "fail_budget_exhausted",
    "get_cabinet_auth_providers",
    "is_allowed_domain",
    "require_email_sign_in",
    "send_limit_hit",
    "telegram_profile_from_oauth",
    "verify_email_code",
]
