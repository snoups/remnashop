from dataclasses import dataclass

from src.application.dto import PaymentGatewayDto
from src.application.dto.payment_gateway import PlategaGatewaySettingsDto
from src.core.enums import PaymentGatewayType


@dataclass(frozen=True)
class PaymentMethodOption:
    id: str
    gateway_type: PaymentGatewayType
    label: str | None = None
    platega_payment_method: int | None = None


def build_payment_method_options(gateways: list[PaymentGatewayDto]) -> list[PaymentMethodOption]:
    options: list[PaymentMethodOption] = []

    for gateway in gateways:
        if (
            gateway.type == PaymentGatewayType.PLATEGA
            and isinstance(gateway.settings, PlategaGatewaySettingsDto)
        ):
            if gateway.settings.sbp_payment_method is not None:
                options.append(
                    PaymentMethodOption(
                        id="PLATEGA:SBP",
                        gateway_type=gateway.type,
                        label="СБП",
                        platega_payment_method=gateway.settings.sbp_payment_method,
                    )
                )

            if gateway.settings.card_payment_method is not None:
                options.append(
                    PaymentMethodOption(
                        id="PLATEGA:CARD",
                        gateway_type=gateway.type,
                        label="Картой",
                        platega_payment_method=gateway.settings.card_payment_method,
                    )
                )

            if gateway.settings.payment_method is not None and not any(
                option.gateway_type == PaymentGatewayType.PLATEGA for option in options
            ):
                options.append(
                    PaymentMethodOption(
                        id=gateway.type.value,
                        gateway_type=gateway.type,
                        platega_payment_method=gateway.settings.payment_method,
                    )
                )
            continue

        options.append(PaymentMethodOption(id=gateway.type.value, gateway_type=gateway.type))

    return options


def find_payment_method_option(
    gateways: list[PaymentGatewayDto],
    option_id: str,
) -> PaymentMethodOption:
    for option in build_payment_method_options(gateways):
        if option.id == option_id:
            return option

    raise ValueError(f"Payment method option '{option_id}' not found")
