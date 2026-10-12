from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, kw_only=True)
class EmailMessageDto:
    to: str
    subject: str
    text: str
    html: str


@dataclass(frozen=True, kw_only=True)
class EmailBrandDto:
    brand: str
    color: Optional[str]
    has_logo: bool
