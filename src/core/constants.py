import re
from datetime import timezone
from pathlib import Path
from re import Pattern
from typing import Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]
ASSETS_DIR: Final[Path] = BASE_DIR / "assets"
LOG_DIR: Final[Path] = BASE_DIR / "logs"

DOMAIN_REGEX: Pattern[str] = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
TAG_REGEX: Pattern[str] = re.compile(r"^[A-Z0-9_]{1,16}$")
URL_PATTERN: Pattern[str] = re.compile(r"^https://\S+$")
USERNAME_PATTERN: Pattern[str] = re.compile(r"^@[a-zA-Z0-9_]{5,32}$")

REPOSITORY: Final[str] = "https://github.com/snoups/remnashop"
T_ME: Final[str] = "https://t.me/"
API_V1: Final[str] = "/api/v1"
BOT_WEBHOOK_PATH: Final[str] = "/telegram"
PAYMENTS_WEBHOOK_PATH: Final[str] = "/payments"
REMNAWAVE_WEBHOOK_PATH: Final[str] = "/remnawave"

IMPORTED_TAG: Final[str] = "IMPORTED"
INLINE_QUERY_INVITE: Final[str] = "invite"
DEEPLINK_PREFIX: Final[str] = "?start="
REMNASHOP_PREFIX: Final[str] = "rs_"
PAYMENT_PREFIX: Final[str] = "payment_"
GOTO_PREFIX: Final[str] = "gt_"
ENCRYPTED_PREFIX: Final[str] = "enc_"
REFERRAL_PREFIX: Final[str] = "ref_"
PLAN_PREFIX: Final[str] = "plan_"

MIDDLEWARE_DATA_KEY: Final[str] = "middleware_data"
CONTAINER_KEY: Final[str] = "dishka_container"
CONFIG_KEY: Final[str] = "config"
USER_KEY: Final[str] = "user"
TARGET_TELEGRAM_ID: Final[str] = "target_telegram_id"

TIMEZONE: Final[timezone] = timezone.utc
DATETIME_FORMAT: Final[str] = "%d.%m.%Y %H:%M:%S"

TIME_1M: Final[int] = 60
TIME_1H: Final[int] = TIME_1M * 60
TIME_1D: Final[int] = TIME_1H * 24

TTL_5M: Final[int] = TIME_1M * 5
TTL_10M: Final[int] = TIME_1M * 10
TTL_30M: Final[int] = TIME_1M * 30
TTL_1H: Final[int] = TIME_1H
TTL_6H: Final[int] = TIME_1H * 6
TTL_12H: Final[int] = TIME_1H * 12
TTL_1D: Final[int] = TIME_1D
TTL_7D: Final[int] = TIME_1D * 7

RECENT_REGISTERED_MAX_COUNT: Final[int] = 25
RECENT_ACTIVITY_MAX_COUNT: Final[int] = 25

BATCH_SIZE_10: Final[int] = 10
BATCH_SIZE_20: Final[int] = 20
BATCH_DELAY: Final[int] = 1
