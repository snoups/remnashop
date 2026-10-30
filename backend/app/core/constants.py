import re
from datetime import timezone
from decimal import Decimal
from pathlib import Path
from re import Pattern
from typing import Any, Final

from packaging.version import Version

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]
REPO_ROOT: Final[Path] = BASE_DIR.parent
ASSETS_DIR: Final[Path] = BASE_DIR / "assets"
MEDIA_DIR: Final[Path] = BASE_DIR / "media"

ONE_CENT: Final[Decimal] = Decimal("0.01")
ZERO_AMOUNT: Final[Decimal] = Decimal(0)
BACKUP_DIR: Final[Path] = MEDIA_DIR / "backups"
LOG_DIR: Final[Path] = BASE_DIR / "logs"

DOMAIN_REGEX: Final[Pattern[str]] = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
LOGIN_PATTERN: Final[Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]+$")

REMNAWAVE_MIN_VERSION: Final[Version] = Version("2.7.0")
REMNAWAVE_MAX_VERSION: Final[Version] = Version("2.8.0")

REPOSITORY: Final[str] = "https://github.com/remnashop/remnashop"
T_ME: Final[str] = "https://t.me/"
API_V1: Final[str] = "/api/v1"
BOT_WEBHOOK_PATH: Final[str] = "/telegram"
# registered in every gateway's dashboard, never rename
PAYMENTS_WEBHOOK_PATH: Final[str] = "/payments"
REMNAWAVE_WEBHOOK_PATH: Final[str] = "/remnawave"

# A window's banner is just a banner name: unset means no banner, DEFAULT_BANNER_NAME
# means the shared one, and anything prefixed with WINDOW_BANNER_PREFIX is that
# window's own. The frontend mirrors both when it uploads or assigns one.
DEFAULT_BANNER_NAME: Final[str] = "default"
WINDOW_BANNER_PREFIX: Final[str] = "win."
# The name lands in a filesystem path; anything outside this alphabet (a slash,
# a leading dot, "..") would let a caller walk out of the media dir.
BANNER_NAME_PATTERN: Final[str] = r"^[a-z0-9][a-z0-9._-]*$"

REMNASHOP_PREFIX: Final[str] = "rs_"
WEB_PREFIX: Final[str] = "web_"
WEBAUTH_START_PREFIX: Final[str] = "webauth_"
PLAN_START_PREFIX: Final[str] = "plan_"
# callback data under a customer's Telegram notification
CUSTOMER_NOTIFICATION_CLOSE_CALLBACK: Final[str] = "cn:close"
CUSTOMER_NOTIFICATION_RENEW_PREFIX: Final[str] = "cn:renew:"
CUSTOMER_NOTIFICATION_BUY_CALLBACK: Final[str] = "cn:buy"

REDIS_KEY_PREFIX: Final[str] = "remnashop:"
# a hung Redis fails fast instead of stalling every request on it; dead pooled
# connections are pinged out before use
REDIS_WAIT_CONNECTION_KWARGS: Final[dict[str, Any]] = {
    "socket_connect_timeout": 5,
    "socket_keepalive": True,
    "health_check_interval": 30,
}
# not for a client that blocks on reads (BRPOP, pub/sub listen): those would
# time out while simply idle
REDIS_CONNECTION_KWARGS: Final[dict[str, Any]] = {
    **REDIS_WAIT_CONNECTION_KWARGS,
    "socket_timeout": 5,
    "retry_on_timeout": True,
}
# one per-account budget for the bot and the cabinet

TELEGRAM_RESTART_CHANNEL: Final[str] = f"{REDIS_KEY_PREFIX}telegram:restart"
TELEGRAM_LOGS_KEY: Final[str] = f"{REDIS_KEY_PREFIX}telegram:logs"
DIALOG_CONFIG_CHANGED_CHANNEL: Final[str] = f"{REDIS_KEY_PREFIX}telegram:dialog-config-changed"
TRANSLATION_CHANGED_CHANNEL: Final[str] = f"{REDIS_KEY_PREFIX}telegram:translation-changed"
PAYMENT_OUTCOME_CHANNEL: Final[str] = f"{REDIS_KEY_PREFIX}telegram:payment-outcome"

# A custom dialog window renders through one state out of a fixed pool
# (app/telegram/dialogs/state_pool.py), so the pool size is also the hard cap on
# how many custom windows a shop can have.
CUSTOM_DIALOG_WINDOW_SLOTS: Final[int] = 50

# largest per-type broadcast media cap; the body-size middleware lets this much through
BROADCAST_MEDIA_MAX_BYTES: Final[int] = 50 * 1024 * 1024

# oauth's callback writes this cookie, auth's /refresh and /logout read it
REFRESH_COOKIE_NAME: Final[str] = "refresh_token"
CSRF_COOKIE_NAME: Final[str] = "csrf_token"
REFRESH_COOKIE_PATH: Final[str] = f"{API_V1}/auth"
DOCS_PATH: Final[str] = f"{API_V1}/docs"
DOCS_COOKIE_NAME: Final[str] = "docs_access"

# Set by the web cabinet's nginx, which overwrites both on every request.
CABINET_CLIENT_IP_HEADER: Final[str] = "x-cabinet-client-ip"
CABINET_PROXY_SECRET_HEADER: Final[str] = "x-cabinet-proxy-secret"

CONTAINER_KEY: Final[str] = "dishka_container"
USER_KEY: Final[str] = "user"

INT32_MAX: Final[int] = 2_147_483_647
# users.points is Numeric(12, 0)
MAX_POINTS_BALANCE: Final[Decimal] = Decimal(10**12 - 1)
INT64_MAX: Final[int] = 2**63 - 1

TIMEZONE: Final[timezone] = timezone.utc
DATETIME_FILE_FORMAT: Final[str] = "%Y-%m-%d_%H-%M-%S"

TIME_1M: Final[int] = 60
TIME_1H: Final[int] = TIME_1M * 60
TIME_1D: Final[int] = TIME_1H * 24

TTL_5M: Final[int] = TIME_1M * 5
TTL_10M: Final[int] = TIME_1M * 10
TTL_15M: Final[int] = TIME_1M * 15
TTL_1H: Final[int] = TIME_1H
TTL_2H: Final[int] = TIME_1H * 2
TTL_1D: Final[int] = TIME_1D
TTL_7D: Final[int] = TIME_1D * 7
TTL_30D: Final[int] = TIME_1D * 30

# Plan.traffic_limit / AddOn.amount are stored as whole GB (binary, matching
# "give this plan 100 GB" as an admin would type it). Remnawave's API takes
# bytes (CreateUserRequestDto.traffic_limit_bytes): convert at the SDK call
# only, never store bytes in our schema.
GB_TO_BYTES: Final[int] = 1024**3

# what Remnawave accepts as a user tag (CreateUserRequestDto.tag); a plan's tag goes
# onto every panel user it provisions
PANEL_TAG_PATTERN: Final[str] = r"^[A-Z0-9_]+$"
PANEL_TAG_MAX_LENGTH: Final[int] = 16

# Cap on what a webhook handler will buffer. Both webhook routes are
# unauthenticated and read the whole body before the signature check, and the
# panel one skips the global rate limiter; without this only the reverse proxy
# bounds it, and the bundled traefik config sets no limit. Well above the
# largest real payload, a Remnawave user event.
MAX_WEBHOOK_BODY_BYTES: Final[int] = 1024 * 1024


DEFAULT_PAGE_SIZE: Final[int] = 50
MAX_PAGE_SIZE: Final[int] = 200
SEARCH_MAX_LENGTH: Final[int] = 200

DEFAULT_ALLOWED_EMAIL_DOMAINS: Final[tuple[str, ...]] = (
    "gmail.com",
    "googlemail.com",
    "yandex.ru",
    "ya.ru",
    "yandex.com",
    "yandex.by",
    "yandex.kz",
    "yandex.ua",
    "mail.ru",
    "inbox.ru",
    "list.ru",
    "bk.ru",
    "internet.ru",
    "rambler.ru",
    "lenta.ru",
    "autorambler.ru",
    "myrambler.ru",
    "ro.ru",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "yahoo.com",
    "ymail.com",
    "aol.com",
    "gmx.de",
    "gmx.net",
    "gmx.com",
    "web.de",
    "t-online.de",
    "orange.fr",
    "libero.it",
)

# an address a customer may type: one @, no spaces or header-breaking characters,
# no "?" (an RFC 2047 encoded word would make one mailbox look like many)
EMAIL_PATTERN: Final[str] = r'^[^@\s(),<>;:"?]+@[^@\s(),<>;:"?]+$'
