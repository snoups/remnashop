from datetime import timezone
from pathlib import Path
from typing import Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]
ASSETS_DIR: Final[Path] = BASE_DIR / "assets"
BANNERS_DIR: Final[Path] = ASSETS_DIR / "banners"
TRANSLATIONS_DIR: Final[Path] = ASSETS_DIR / "translations"
LOG_DIR: Final[Path] = BASE_DIR / "logs"

DOMAIN_REGEX: Final[str] = r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$"
API_V1: Final[str] = "/api/v1"
BOT_WEBHOOK_PATH: Final[str] = "/telegram"
PAYMENTS_WEBHOOK_PATH: Final[str] = "/payments"

TIMEZONE: Final[timezone] = timezone.utc
REMNASHOP_TAG: Final[str] = "rs_"

CONTAINER_KEY: Final[str] = "dishka_container"
CONFIG_KEY: Final[str] = "config"
USER_KEY: Final[str] = "user"

TIME_1M: Final[int] = 60
TIME_5M: Final[int] = TIME_1M * 5
TIME_10M: Final[int] = TIME_1M * 10

# TODO: Check with a large number of users
RECENT_REGISTERED_MAX_COUNT: Final[int] = 10
RECENT_ACTIVITY_MAX_COUNT: Final[int] = 10
