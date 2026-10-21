from typing import Final, NewType, Optional, Self

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from app.core.enums import PaymentGatewayType
from app.core.exceptions import PaymentGatewayError

# digits as the admin typed them; a provider gets the exact text back
NumericStr = NewType("NumericStr", str)


class GatewaySettings(BaseModel):
    """A gateway's dashboard fields; the dashboard catalog is built from them."""

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_values(cls, values: dict[str, str]) -> Self:
        # a blank field is an unset one
        present = {key: value for key, value in values.items() if value.strip()}
        try:
            return cls.model_validate(present)
        except ValidationError as error:
            missing = ", ".join(str(e["loc"][0]) for e in error.errors() if e["loc"])
            raise PaymentGatewayError(
                f"{cls.__name__}: invalid or missing setting(s) {missing}"
            ) from None


class TelegramStarsSettings(GatewaySettings):
    require_paid_purchase: bool = False


class YooKassaSettings(GatewaySettings):
    shop_id: str
    api_key: SecretStr
    vat_code: Optional[NumericStr] = None
    verify_ip: bool = True


class YooMoneySettings(GatewaySettings):
    wallet_id: str
    secret_key: SecretStr
    access_token: Optional[SecretStr] = None


class CryptomusSettings(GatewaySettings):
    merchant_id: str
    api_key: SecretStr
    currency: Optional[str] = None


class HeleketSettings(CryptomusSettings): ...


class CryptoPaySettings(GatewaySettings):
    api_key: SecretStr
    currency: Optional[str] = None


class FreeKassaSettings(GatewaySettings):
    shop_id: NumericStr
    api_key: SecretStr
    secret_word_2: SecretStr
    payment_system_id: NumericStr


class MulenPaySettings(GatewaySettings):
    api_key: SecretStr
    secret_key: SecretStr
    shop_id: NumericStr
    vat_code: Optional[NumericStr] = None


class PayMasterSettings(GatewaySettings):
    merchant_id: str
    api_key: SecretStr


class PlategaSettings(GatewaySettings):
    merchant_id: str
    api_key: SecretStr
    payment_method: Optional[NumericStr] = None


class RobokassaSettings(GatewaySettings):
    merchant_login: str
    password1: SecretStr
    password2: SecretStr


class UrlPaySettings(GatewaySettings):
    shop_id: NumericStr
    api_key: SecretStr
    secret_key: SecretStr
    vat_code: Optional[NumericStr] = None


class WataSettings(GatewaySettings):
    api_key: SecretStr
    currency: Optional[str] = None


class ValutixSettings(GatewaySettings):
    api_key: SecretStr
    service_id: Optional[NumericStr] = None
    currency: Optional[str] = None

    @property
    def token(self) -> SecretStr:
        return self.api_key


class RollyPaySettings(GatewaySettings):
    api_key: SecretStr
    signing_secret: SecretStr
    currency: Optional[str] = None


class AntilopaySettings(GatewaySettings):
    secret_id: str
    private_key: SecretStr
    public_key: SecretStr
    project_id: str
    currency: Optional[str] = None


class PaypalychSettings(GatewaySettings):
    api_token: SecretStr
    shop_id: str
    currency: Optional[str] = None


class RioPaySettings(GatewaySettings):
    api_token: SecretStr
    service_id: Optional[NumericStr] = None
    currency: Optional[str] = None

    @property
    def token(self) -> SecretStr:
        return self.api_token


class AuraPaySettings(GatewaySettings):
    api_key: SecretStr
    shop_id: str
    secret_key: SecretStr


class SeverPaySettings(GatewaySettings):
    mid: NumericStr
    token: SecretStr
    currency: Optional[str] = None


class LavaSettings(GatewaySettings):
    shop_id: str
    secret_key: SecretStr
    webhook_secret: SecretStr


class CloudPaymentsSettings(GatewaySettings):
    public_id: str
    api_secret: SecretStr
    currency: Optional[str] = None


class PayPearSettings(GatewaySettings):
    shop_id: str
    secret_key: SecretStr
    currency: Optional[str] = None


GATEWAY_SETTINGS: Final[dict[PaymentGatewayType, type[GatewaySettings]]] = {
    PaymentGatewayType.TELEGRAM_STARS: TelegramStarsSettings,
    PaymentGatewayType.YOOKASSA: YooKassaSettings,
    PaymentGatewayType.YOOMONEY: YooMoneySettings,
    PaymentGatewayType.CRYPTOMUS: CryptomusSettings,
    PaymentGatewayType.HELEKET: HeleketSettings,
    PaymentGatewayType.CRYPTOPAY: CryptoPaySettings,
    PaymentGatewayType.FREEKASSA: FreeKassaSettings,
    PaymentGatewayType.MULENPAY: MulenPaySettings,
    PaymentGatewayType.PAYMASTER: PayMasterSettings,
    PaymentGatewayType.PLATEGA: PlategaSettings,
    PaymentGatewayType.ROBOKASSA: RobokassaSettings,
    PaymentGatewayType.URLPAY: UrlPaySettings,
    PaymentGatewayType.WATA: WataSettings,
    PaymentGatewayType.VALUTIX: ValutixSettings,
    PaymentGatewayType.ROLLYPAY: RollyPaySettings,
    PaymentGatewayType.ANTILOPAY: AntilopaySettings,
    PaymentGatewayType.PAYPALYCH: PaypalychSettings,
    PaymentGatewayType.RIOPAY: RioPaySettings,
    PaymentGatewayType.AURAPAY: AuraPaySettings,
    PaymentGatewayType.SEVERPAY: SeverPaySettings,
    PaymentGatewayType.LAVA: LavaSettings,
    PaymentGatewayType.CLOUDPAYMENTS: CloudPaymentsSettings,
    PaymentGatewayType.PAYPEAR: PayPearSettings,
}
