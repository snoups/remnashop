from dataclasses import dataclass, fields
from typing import Any, Literal, Optional, Union
from uuid import UUID

from pydantic import SecretStr

from src.core.enums import Currency, PaymentGatewayType

from .base import BaseDto, TrackableMixin


@dataclass(kw_only=True)
class PaymentResultDto:
    id: UUID
    url: Optional[str] = None


@dataclass(kw_only=True)
class PaymentGatewayDto(BaseDto, TrackableMixin):
    order_index: int = 0
    type: PaymentGatewayType
    currency: Currency

    is_active: bool = False
    settings: Optional["AnyGatewaySettingsDto"] = None

    @property
    def requires_webhook(self) -> bool:
        return self.type not in {
            PaymentGatewayType.CRYPTOMUS,
            PaymentGatewayType.HELEKET,
            PaymentGatewayType.FREEKASSA,
            PaymentGatewayType.PAYMASTER,
        }


@dataclass(kw_only=True)
class GatewaySettingsDto(TrackableMixin):
    @property
    def is_configured(self) -> bool:
        for f in fields(self):
            if f.name in {"created_at", "updated_at", "type"}:
                continue
            if getattr(self, f.name) is None:
                return False
        return True

    @property
    def as_list(self) -> list[dict[str, Any]]:
        return [
            {"field": f.name, "value": getattr(self, f.name)}
            for f in fields(self)
            if f.name not in {"type", "created_at", "updated_at"} and not f.name.startswith("_")
        ]


@dataclass(kw_only=True)
class YooKassaGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.YOOKASSA] = PaymentGatewayType.YOOKASSA
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    customer: Optional[str] = None
    vat_code: Optional[int] = None


@dataclass(kw_only=True)
class YooMoneyGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.YOOMONEY] = PaymentGatewayType.YOOMONEY
    wallet_id: Optional[str] = None
    secret_key: Optional[SecretStr] = None


@dataclass(kw_only=True)
class CryptomusGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.CRYPTOMUS] = PaymentGatewayType.CRYPTOMUS
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


@dataclass(kw_only=True)
class HeleketGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.HELEKET] = PaymentGatewayType.HELEKET
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


@dataclass(kw_only=True)
class CryptoPayGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.CRYPTOPAY] = PaymentGatewayType.CRYPTOPAY
    shop_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


@dataclass(kw_only=True)
class FreeKassaGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.FREEKASSA] = PaymentGatewayType.FREEKASSA
    shop_id: Optional[int] = None
    api_key: Optional[SecretStr] = None
    secret_word_2: Optional[SecretStr] = None
    payment_system_id: Optional[int] = None
    customer_email: Optional[str] = None
    customer_ip: Optional[str] = None


@dataclass(kw_only=True)
class MulenPayGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.MULENPAY] = PaymentGatewayType.MULENPAY
    api_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None
    shop_id: Optional[int] = None
    vat_code: Optional[int] = None


@dataclass(kw_only=True)
class PayMasterGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.PAYMASTER] = PaymentGatewayType.PAYMASTER
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None


@dataclass(kw_only=True)
class PlategaGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.PLATEGA] = PaymentGatewayType.PLATEGA
    merchant_id: Optional[str] = None
    api_key: Optional[SecretStr] = None
    payment_method: Optional[int] = None


@dataclass(kw_only=True)
class RoboKassaGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.ROBOKASSA] = PaymentGatewayType.ROBOKASSA
    merchant_login: Optional[str] = None
    password1: Optional[SecretStr] = None
    password2: Optional[SecretStr] = None


@dataclass(kw_only=True)
class UrlPayGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.URLPAY] = PaymentGatewayType.URLPAY
    shop_id: Optional[int] = None
    api_key: Optional[SecretStr] = None
    secret_key: Optional[SecretStr] = None
    vat_code: Optional[int] = None


@dataclass(kw_only=True)
class WataGatewaySettingsDto(GatewaySettingsDto):
    type: Literal[PaymentGatewayType.WATA] = PaymentGatewayType.WATA
    api_key: Optional[SecretStr] = None


AnyGatewaySettingsDto = Union[
    YooKassaGatewaySettingsDto,
    YooMoneyGatewaySettingsDto,
    CryptomusGatewaySettingsDto,
    HeleketGatewaySettingsDto,
    CryptoPayGatewaySettingsDto,
    FreeKassaGatewaySettingsDto,
    MulenPayGatewaySettingsDto,
    PayMasterGatewaySettingsDto,
    PlategaGatewaySettingsDto,
    RoboKassaGatewaySettingsDto,
    UrlPayGatewaySettingsDto,
    WataGatewaySettingsDto,
]
