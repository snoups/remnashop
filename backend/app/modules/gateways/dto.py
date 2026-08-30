from dataclasses import dataclass

from app.core.dto import BaseDto, TimestampMixin
from app.core.enums import PaymentGatewayType


class PaymentGatewayDto(BaseDto, TimestampMixin):
    type: PaymentGatewayType
    order_index: int = 0
    is_active: bool = False
    is_configured: bool = False


@dataclass(frozen=True, kw_only=True)
class UpdateGatewaySettingsDto:
    type: PaymentGatewayType
    values: dict[str, str]


@dataclass(frozen=True, kw_only=True)
class ReorderGatewaysDto:
    ordered_types: list[PaymentGatewayType]
