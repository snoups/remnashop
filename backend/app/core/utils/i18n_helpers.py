from datetime import datetime
from typing import Final, Optional

_EXPIRE_TIME_FORMAT: Final[str] = "%d.%m.%Y %H:%M"


def i18n_format_expire_time(expiry: Optional[datetime]) -> str:
    if expiry is None:
        return "—"
    return expiry.strftime(_EXPIRE_TIME_FORMAT)


def i18n_format_traffic_limit(value: int) -> str:
    if not value:
        return "Unlimited"
    return f"{value} GB"


def i18n_format_device_limit(value: int) -> str:
    if not value:
        return "Unlimited"
    return f"{value} devices"
