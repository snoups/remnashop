from typing import Final

from app.core.error_codes import ErrorCode

# the codes that count as a failed attempt for a step's failure_rate_limit;
# sign-in and account linking share them
BOT_SIGNIN_FAILURES: Final[frozenset[ErrorCode]] = frozenset({ErrorCode.DEEPLINK_EXPIRED})
TELEGRAM_FAILURES: Final[frozenset[ErrorCode]] = frozenset({ErrorCode.INVALID_INIT_DATA})
EMAIL_VERIFY_FAILURES: Final[frozenset[ErrorCode]] = frozenset(
    {ErrorCode.EMAIL_CODE_INVALID, ErrorCode.EMAIL_CODE_EXPIRED}
)
OAUTH_CALLBACK_FAILURES: Final[frozenset[ErrorCode]] = frozenset(
    {ErrorCode.OAUTH_STATE_INVALID, ErrorCode.OAUTH_CODE_EXCHANGE_FAILED}
)
