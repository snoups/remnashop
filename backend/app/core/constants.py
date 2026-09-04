import re
from datetime import timezone
from pathlib import Path
from re import Pattern
from typing import Final

from packaging.version import Version

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]
REPO_ROOT: Final[Path] = BASE_DIR.parent
ASSETS_DIR: Final[Path] = BASE_DIR / "assets"
MEDIA_DIR: Final[Path] = BASE_DIR / "media"
BACKUP_DIR: Final[Path] = MEDIA_DIR / "backups"
LOG_DIR: Final[Path] = BASE_DIR / "logs"

DOMAIN_REGEX: Final[Pattern[str]] = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
LOGIN_PATTERN: Final[Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]+$")

REMNAWAVE_MIN_VERSION: Final[Version] = Version("2.7.0")
REMNAWAVE_MAX_VERSION: Final[Version] = Version("2.8.0")

REPOSITORY: Final[str] = "https://github.com/snoups/remnashop"
DOCS: Final[str] = "https://remnashop.dev"
T_ME: Final[str] = "https://t.me/"
API_V1: Final[str] = "/api/v1"
BOT_WEBHOOK_PATH: Final[str] = "/telegram"
PAYMENTS_WEBHOOK_PATH: Final[str] = "/payments"
REMNAWAVE_WEBHOOK_PATH: Final[str] = "/remnawave"

IMPORTED_TAG: Final[str] = "IMPORTED"
INLINE_QUERY_INVITE: Final[str] = "invite"
REMNASHOP_PREFIX: Final[str] = "rs_"
WEB_PREFIX: Final[str] = "web_"
PAYMENT_PREFIX: Final[str] = "payment_"
GOTO_PREFIX: Final[str] = "gt_"
ENCRYPTED_PREFIX: Final[str] = "enc_"

REDIS_KEY_PREFIX: Final[str] = "remnashop:"

TELEGRAM_RESTART_CHANNEL: Final[str] = f"{REDIS_KEY_PREFIX}telegram:restart"
DIALOG_CONFIG_CHANGED_CHANNEL: Final[str] = f"{REDIS_KEY_PREFIX}telegram:dialog-config-changed"

# Shared between auth's /refresh, /logout and oauth's /oauth/{provider}/callback --
# oauth writes this cookie, auth reads it.
REFRESH_COOKIE_NAME: Final[str] = "refresh_token"
CSRF_COOKIE_NAME: Final[str] = "csrf_token"
REFRESH_COOKIE_PATH: Final[str] = "/api/v1/auth"

MIDDLEWARE_DATA_KEY: Final[str] = "middleware_data"
CONTAINER_KEY: Final[str] = "dishka_container"
CONFIG_KEY: Final[str] = "config"
USER_KEY: Final[str] = "user"
TARGET_TELEGRAM_ID: Final[str] = "target_telegram_id"
TARGET_USER_ID: Final[str] = "target_user_id"
FROM_REFERRAL_USER_ID: Final[str] = "from_referral_user_id"
USER_LIST_ORIGIN: Final[str] = "user_list_origin"
USER_LIST_PAYLOAD: Final[str] = "user_list_payload"

INT32_MAX: Final[int] = 2_147_483_647

TIMEZONE: Final[timezone] = timezone.utc
DATETIME_VIEW_FORMAT: Final[str] = "%d.%m.%y %H:%M:%S"
DATETIME_FILE_FORMAT: Final[str] = "%Y-%m-%d_%H-%M-%S"

TIME_1M: Final[int] = 60
TIME_1H: Final[int] = TIME_1M * 60
TIME_1D: Final[int] = TIME_1H * 24

TTL_5M: Final[int] = TIME_1M * 5
TTL_10M: Final[int] = TIME_1M * 10
TTL_15M: Final[int] = TIME_1M * 15
TTL_30M: Final[int] = TIME_1M * 30
TTL_1H: Final[int] = TIME_1H
TTL_6H: Final[int] = TIME_1H * 6
TTL_12H: Final[int] = TIME_1H * 12
TTL_1D: Final[int] = TIME_1D
TTL_7D: Final[int] = TIME_1D * 7
TTL_30D: Final[int] = TIME_1D * 30

UNLIMITED_EXPIRE_YEAR: Final[int] = 2099

BATCH_SIZE_10: Final[int] = 10
BATCH_SIZE_20: Final[int] = 20
BATCH_DELAY: Final[int] = 1

# Plan.traffic_limit / AddOn.amount are stored as whole GB (binary, matching
# "give this plan 100 GB" as an admin would type it) -- Remnawave's own API
# is byte-denominated (CreateUserRequestDto.traffic_limit_bytes). Convert at
# the SDK-call boundary only; never store bytes anywhere in our own schema.
GB_TO_BYTES: Final[int] = 1024**3
