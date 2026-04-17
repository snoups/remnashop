import re
from datetime import timezone
from pathlib import Path
from re import Pattern
from typing import Final

from packaging.version import Version

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]
ASSETS_DIR: Final[Path] = BASE_DIR / "assets"
BACKUP_DIR: Final[Path] = BASE_DIR / "backups"
LOG_DIR: Final[Path] = BASE_DIR / "logs"

DOMAIN_REGEX: Pattern[str] = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
TAG_REGEX: Pattern[str] = re.compile(r"^[A-Z0-9_]{1,16}$")
URL_PATTERN: Pattern[str] = re.compile(r"^https://\S+$")
USERNAME_PATTERN: Pattern[str] = re.compile(r"^@[a-zA-Z0-9_]{5,32}$")

REMNAWAVE_MIN_VERSION: Final[Version] = Version("2.7.0")
REMNAWAVE_MAX_VERSION: Final[Version] = Version("2.8.0")

REPOSITORY: Final[str] = "https://github.com/snoups/remnashop"
DOCS: Final[str] = "https://remnashop.mintlify.app"
T_ME: Final[str] = "https://t.me/"
API_V1: Final[str] = "/api/v1"
BOT_WEBHOOK_PATH: Final[str] = "/telegram"
PAYMENTS_WEBHOOK_PATH: Final[str] = "/payments"
REMNAWAVE_WEBHOOK_PATH: Final[str] = "/remnawave"

IMPORTED_TAG: Final[str] = "IMPORTED"
INLINE_QUERY_INVITE: Final[str] = "invite"
REMNASHOP_PREFIX: Final[str] = "rs_"
PAYMENT_PREFIX: Final[str] = "payment_"
GOTO_PREFIX: Final[str] = "gt_"
ENCRYPTED_PREFIX: Final[str] = "enc_"

MIDDLEWARE_DATA_KEY: Final[str] = "middleware_data"
CONTAINER_KEY: Final[str] = "dishka_container"
CONFIG_KEY: Final[str] = "config"
USER_KEY: Final[str] = "user"
TARGET_TELEGRAM_ID: Final[str] = "target_telegram_id"

TIMEZONE: Final[timezone] = timezone.utc
DATETIME_VIEW_FORMAT: Final[str] = "%d.%m.%y %H:%M:%S"
DATETIME_FILE_FORMAT: Final[str] = "%Y-%m-%d_%H-%M-%S"

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

TEXT_MAX_LENGTH: Final[int] = 4096
TEXT_MEDIA_MAX_LENGTH: Final[int] = 1024
