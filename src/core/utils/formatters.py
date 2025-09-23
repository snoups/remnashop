from __future__ import annotations

from typing import TYPE_CHECKING, Final, Optional, Union

if TYPE_CHECKING:
    from src.infrastructure.database.models.dto import UserDto

from decimal import ROUND_HALF_UP, ROUND_UP, Decimal

from src.core.i18n_keys import ByteUnitKey, TimeUnitKey, UtilKey


def format_log_user(user: UserDto) -> str:
    return f"[{user.role.upper()}:{user.telegram_id} ({user.name})]"


def format_device_count(value: int) -> int:
    if value == -1:  # UNLIMITED
        return 0

    return value


def format_gb_to_bytes(value: int, *, binary: bool = True) -> int:
    gb_value = Decimal(value)

    if gb_value == -1:  # UNLIMITED
        return 0

    multiplier = Decimal(1024**3) if binary else Decimal(10**9)
    bytes_value = (gb_value * multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    return max(0, int(bytes_value))


def format_percent(part: int, whole: int) -> str:
    if whole == 0:
        return "N/A"

    percent = (part / whole) * 100
    return f"{percent:.2f}"


def format_country_code(code: str) -> str:
    if not code.isalpha() or len(code) != 2:
        return "🏴‍☠️"

    return "".join(chr(ord("🇦") + ord(c.upper()) - ord("A")) for c in code)


def i18n_format_bytes_to_gb(
    value: Optional[Union[int, float]],
    *,
    round_up: bool = False,
    min_unit: ByteUnitKey = ByteUnitKey.GIGABYTE,
) -> tuple[str, dict[str, float]]:
    if not value or value == 0:  # UNLIMITED
        return UtilKey.UNLIMITED, {}

    bytes_value = Decimal(value)
    units: Final[list[ByteUnitKey]] = list(reversed(list(ByteUnitKey)))

    for unit in units:
        if bytes_value >= 1024:
            bytes_value /= Decimal(1024)
        else:
            if units.index(unit) <= units.index(min_unit):
                rounding = ROUND_UP if round_up else ROUND_HALF_UP
                size_formatted = bytes_value.quantize(Decimal("0.01"), rounding=rounding)
                return unit, {"value": float(size_formatted)}

    rounding = ROUND_UP if round_up else ROUND_HALF_UP
    size_formatted = bytes_value.quantize(Decimal("0.01"), rounding=rounding)
    return min_unit, {"value": float(size_formatted)}


def i18n_format_seconds_to_duration(
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


def i18n_format_days_to_duration(value: int) -> tuple[str, dict[str, int]]:
    if value == -1:  # UNLIMITED
        return UtilKey.UNLIMITED, {}

    if value % 365 == 0:
        return TimeUnitKey.YEAR, {"value": value // 365}

    if value % 30 == 0:
        return TimeUnitKey.MONTH, {"value": value // 30}

    return TimeUnitKey.DAY, {"value": value}
