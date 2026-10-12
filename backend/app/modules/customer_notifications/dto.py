from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class NotifyCustomerDto:
    user_id: int
    event_type: str
    outbox_id: int
    args: dict[str, str | int]


@dataclass(frozen=True, kw_only=True)
class SendCustomerTelegramDto:
    user_id: int
    text: str
