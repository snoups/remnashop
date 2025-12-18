from typing import Annotated, Any, Literal, Optional, Union
from uuid import UUID

from pydantic import ConfigDict, Field, SecretStr

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
    model_config = ConfigDict(validate_assignment=True)

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
    type: Literal[PaymentGatewayType.YOOKASSA] = PaymentGatewayType.YOOKASSA
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    customer: Optional[str] = None
    vat_code: Optional[YookassaVatCode] = None


class YoomoneyGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.YOOMONEY] = PaymentGatewayType.YOOMONEY
    wallet_id: Optional[str] = None
    secret_key: Optional[SecretStr] = None


class CryptomusGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.CRYPTOMUS] = PaymentGatewayType.CRYPTOMUS
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


class HeleketGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.HELEKET] = PaymentGatewayType.HELEKET
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


class CryptopayGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.CRYPTOPAY] = PaymentGatewayType.CRYPTOPAY
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None


class RobokassaGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.ROBOKASSA] = PaymentGatewayType.ROBOKASSA
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None


AnyGatewaySettingsDto = Annotated[
    Union[
        YookassaGatewaySettingsDto,
        YoomoneyGatewaySettingsDto,
        CryptomusGatewaySettingsDto,
        HeleketGatewaySettingsDto,
        CryptopayGatewaySettingsDto,
        RobokassaGatewaySettingsDto,
    ],
    Field(discriminator="type"),
]
