from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class EmailMessageDto:
    to: str
    subject: str
    text: str
    html: str
