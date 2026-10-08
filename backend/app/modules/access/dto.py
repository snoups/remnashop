from dataclasses import dataclass
from typing import Optional

from app.core.enums import AdLinkChannel


@dataclass(frozen=True, kw_only=True)
class CheckRegistrationAccessDto:
    channel: AdLinkChannel
    telegram_id: Optional[int] = None
    referral_code: Optional[str] = None
    ad_link_code: Optional[str] = None
