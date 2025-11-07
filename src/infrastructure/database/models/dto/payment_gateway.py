from typing import Any, Optional, Union
from uuid import UUID

from pydantic import Field, SecretStr

from src.core.enums import Currency, PaymentGatewayType, YookassaVatCode

from .base import TrackableDto


class PaymentResult(TrackableDto):
    id: UUID
    url: Optional[str] = None


class PaymentGatewayDto(TrackableDto):
    id: Optional[int] = Field(default=None, frozen=True)

    order_index: int
    type: PaymentGatewayType
    currency: Currency

    is_active: bool
    settings: Optional["AnyGatewaySettingsDto"] = None


class GatewaySettingsDto(TrackableDto):
    @property
    def is_configure(self) -> bool:
        for name, value in self.__dict__.items():
            if value is None:
                return False
        return True

    @property
    def get_settings_as_list_data(self) -> list[dict[str, Any]]:
        return [
            {"field": field_name, "value": value}
            for field_name, value in self.__dict__.items()
            if field_name != "type"
        ]


class YookassaGatewaySettingsDto(GatewaySettingsDto):
    type: PaymentGatewayType = PaymentGatewayType.YOOKASSA
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    customer: Optional[str] = None
    vat_code: Optional[YookassaVatCode] = None


class YoomoneyGatewaySettingsDto(GatewaySettingsDto):
    type: PaymentGatewayType = PaymentGatewayType.YOOMONEY
    wallet_id: Optional[str] = None
    secret_key: Optional[SecretStr] = None


class CryptomusGatewaySettingsDto(GatewaySettingsDto):
    type: PaymentGatewayType = PaymentGatewayType.CRYPTOMUS
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


class HeleketGatewaySettingsDto(GatewaySettingsDto):
    type: PaymentGatewayType = PaymentGatewayType.HELEKET
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


class CryptopayGatewaySettingsDto(GatewaySettingsDto):
    type: PaymentGatewayType = PaymentGatewayType.CRYPTOPAY
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None


class RobokassaGatewaySettingsDto(GatewaySettingsDto):
    type: PaymentGatewayType = PaymentGatewayType.ROBOKASSA
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None


AnyGatewaySettingsDto = Union[
    YookassaGatewaySettingsDto,
    YoomoneyGatewaySettingsDto,
    CryptomusGatewaySettingsDto,
    HeleketGatewaySettingsDto,
    CryptopayGatewaySettingsDto,
    RobokassaGatewaySettingsDto,
]
