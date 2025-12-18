from __future__ import annotations

from typing import TYPE_CHECKING, Final, Optional, Union

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto import UserDto

import html
import re
import unicodedata
from calendar import monthrange
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal
from re import Match
from urllib.parse import quote

from src.core.constants import T_ME
from src.core.enums import PlanType
from src.core.i18n.keys import ByteUnitKey, TimeUnitKey, UtilKey
from src.core.utils.time import datetime_now
from src.infrastructure.database.models.dto.user import BaseUserDto

_HTML_RE = re.compile(r"<[^>]*>")
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.|tg://|t\.me/|telegram\.me/|joinchat/)\S+")
_USER_NAME_PLACEHOLDER = "User123"


# For only user action
def format_user_log(user: Union[BaseUserDto, UserDto]) -> str:
    return f"[{user.role.upper()}:{user.telegram_id} ({user.name})]"


def format_user_name(name: Optional[str]) -> str:
    if not name:
        return _USER_NAME_PLACEHOLDER

    text = html.unescape(name)
    text = unicodedata.normalize("NFKC", text)

    text = _HTML_RE.sub("", text)
    text = _URL_RE.sub("", text)

    allowed_prefixes = {"L", "N"}
    allowed_symbols = {"$", "_", "-", "."}

    chars: list[str] = []

    for char in text:
        cat = unicodedata.category(char)

        if cat == "Mn":
            continue

        if cat[0] in allowed_prefixes or char in allowed_symbols or cat == "Zs":
            chars.append(char)

    cleaned = " ".join("".join(chars).split())

    if not cleaned:
        return _USER_NAME_PLACEHOLDER

    if len(cleaned) > 32:
        cleaned = f"{cleaned[:31]}"

    return cleaned


def format_username_to_url(username: str, text: Optional[str]) -> str:
    clean_username = username.lstrip("@")
    encoded_text = quote(text or "")
    return f"{T_ME}{clean_username}?text={encoded_text}"


def format_days_to_datetime(value: int, year: int = 2099) -> datetime:
    dt = datetime_now()

    if value == -1:  # UNLIMITED for panel
        try:
            return dt.replace(year=year)
        except ValueError:
            last_day = monthrange(year, dt.month)[1]
            return dt.replace(year=year, day=min(dt.day, last_day))

    return dt + timedelta(days=value)


def format_device_count(value: Optional[int]) -> int:
    if value == 0 or value is None:
        return -1  # UNLIMITED for bot

    if value == -1:
        return 0  # UNLIMITED for panel

    return value


def format_gb_to_bytes(value: int, *, binary: bool = True) -> int:
    gb_value = Decimal(value)

    if gb_value == -1:
        return 0  # UNLIMITED for panel

    multiplier = Decimal(1024**3) if binary else Decimal(10**9)
    bytes_value = (gb_value * multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    return max(0, int(bytes_value))


def format_bytes_to_gb(value: Optional[int], *, binary: bool = True) -> int:
    if not value or value == 0:
        return -1  # UNLIMITED for bot

    bytes_value = Decimal(value)

    multiplier = Decimal(1024**3) if binary else Decimal(10**9)
    gb_value = (bytes_value / multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    return max(0, int(gb_value))


def format_limits_to_plan_type(traffic: int, devices: int) -> PlanType:
    has_traffic = traffic > 0
    has_devices = devices > 0

    if has_traffic and has_devices:
        return PlanType.BOTH
    elif has_traffic:
        return PlanType.TRAFFIC
    elif has_devices:
        return PlanType.DEVICES
    else:
        return PlanType.UNLIMITED


def format_percent(part: int, whole: int) -> str:
    if whole == 0:
        return "N/A"

    percent = (part / whole) * 100
    return f"{percent:.2f}"


def format_country_code(code: str) -> str:
    if not code.isalpha() or len(code) != 2:
        return "🏴‍☠️"

    return "".join(chr(ord("🇦") + ord(c.upper()) - ord("A")) for c in code)


def i18n_format_bytes_to_unit(
    value: Optional[Union[int, float]],
    *,
    round_up: bool = False,
    min_unit: ByteUnitKey = ByteUnitKey.GIGABYTE,
) -> tuple[str, dict[str, float]]:
    if value == -1:
        return UtilKey.UNLIMITED, {}

    if not value:
        value = 0

    bytes_value = Decimal(value)
    units: Final[list[ByteUnitKey]] = list(ByteUnitKey)  # [B, KB, MB, GB]

    for i, unit in enumerate(units):
        if i + 1 < len(units):
            next_unit_threshold = Decimal(1024)
            if bytes_value >= next_unit_threshold:
                bytes_value /= Decimal(1024)
            else:
                break

    if units.index(unit) < units.index(min_unit):
        unit = min_unit
        factor = Decimal(1024) ** (units.index(min_unit))
        bytes_value = Decimal(value) / factor

    rounding = ROUND_UP if round_up else ROUND_HALF_UP
    size_formatted = bytes_value.quantize(Decimal("0.01"), rounding=rounding)

    return unit, {"value": float(size_formatted)}


def i18n_format_seconds(
    value: Union[int, float, str],
) -> list[tuple[str, dict[str, int]]]:
    remaining = int(value)
    parts = []

    if remaining < 60:
        return [(TimeUnitKey.MINUTE, {"value": 0})]

    units: dict[str, int] = {
        TimeUnitKey.DAY: 86400,
        TimeUnitKey.HOUR: 3600,
        TimeUnitKey.MINUTE: 60,
    }

    for unit, unit_seconds in units.items():
        value = remaining // unit_seconds
        if value > 0:
            parts.append((unit, {"value": value}))
            remaining %= unit_seconds

    if not parts:
        return [(TimeUnitKey.MINUTE, {"value": 1})]

    return parts


def i18n_format_days(value: int) -> tuple[str, dict[str, int]]:
    if value == -1:  # UNLIMITED
        return UtilKey.UNLIMITED, {}

    if value % 365 == 0:
        return TimeUnitKey.YEAR, {"value": value // 365}

    if value % 30 == 0:
        return TimeUnitKey.MONTH, {"value": value // 30}

    return TimeUnitKey.DAY, {"value": value}


def i18n_format_limit(value: int) -> tuple[str, dict[str, int]]:
    return UtilKey.UNIT_UNLIMITED, {"value": value}


def i18n_format_traffic_limit(value: int) -> tuple[str, dict[str, int]]:
    if value == -1:
        return UtilKey.UNIT_UNLIMITED, {"value": value}

    return ByteUnitKey.GIGABYTE, {"value": value}


def i18n_format_device_limit(value: int) -> tuple[str, dict[str, int]]:
    return UtilKey.UNIT_UNLIMITED, {"value": value}


def i18n_format_expire_time(expiry: Union[timedelta, datetime]) -> list[tuple[str, dict[str, int]]]:
    # Special case: unlimited remnawave ;D
    if isinstance(expiry, datetime) and expiry.year == 2099:
        return [(UtilKey.UNLIMITED, {"value": -1})]

    # Convert datetime to timedelta
    if isinstance(expiry, datetime):
        now = datetime_now()
        delta = expiry - now
    else:
        delta = expiry

    if delta.total_seconds() <= 0:
        # Already expired or zero, default to 1 minute
        return [("unknown", {"value": 0})]

    days = delta.days
    seconds = delta.seconds
    parts: list[tuple[str, dict[str, int]]] = []

    # Years
    years, days = divmod(days, 365)
    if years:
        parts.append((TimeUnitKey.YEAR, {"value": years}))

    # Remaining days
    if days:
        parts.append((TimeUnitKey.DAY, {"value": days}))

    # Hours
    hours, seconds = divmod(seconds, 3600)
    if hours:
        parts.append((TimeUnitKey.HOUR, {"value": hours}))

    # Minutes
    minutes, _ = divmod(seconds, 60)
    if minutes:
        parts.append((TimeUnitKey.MINUTE, {"value": minutes}))

    # Default to 1 minute if everything is zero
    return parts or [("unknown", {"value": 0})]


def i18n_postprocess_text(text: str, collapse_level: int = 2) -> str:
    def collapse_html_tags(txt: str) -> str:
        pattern = r"<(\w+)>[\n\r]+(.*?)[\n\r]+</\1>"

        def tag_replacer(match: Match[str]) -> str:
            tag = match[1]
            content = match[2].rstrip()
            return f"<{tag}>{content}</{tag}>"

        return re.sub(pattern, tag_replacer, txt, flags=re.DOTALL)

    def normalize_newlines(txt: str) -> str:
        max_newlines = "\n" * collapse_level
        pattern = rf"(?:\n[ \t]*){{{collapse_level + 1},}}"
        return re.sub(pattern, max_newlines, txt)

    def remove_empty_markers(txt: str) -> str:
        return re.sub(r"\s*!empty!\s*", "", txt)

    text = collapse_html_tags(text)
    text = normalize_newlines(text)
    text = remove_empty_markers(text)

    return text
