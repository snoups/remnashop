from typing import Any

from aiogram_dialog import DialogManager
from dishka import FromDishka
from dishka.integrations.aiogram_dialog import inject
from loguru import logger

from src.core.enums import Currency
from src.infrastructure.database.models.dto import PaymentGatewayDto
from src.services.payment_gateway import PaymentGatewayService


@inject
async def gateways_getter(
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    **kwargs: Any,
) -> dict[str, Any]:
    gateways: list[PaymentGatewayDto] = await payment_gateway_service.get_all()

    formatted_gateways = [
        {
            "id": gateway.id,
            "gateway_type": gateway.type,
            "is_active": gateway.is_active,
        }
        for gateway in gateways
    ]

    return {
        "gateways": formatted_gateways,
    }


@inject
async def gateway_getter(
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    **kwargs: Any,
) -> dict[str, Any]:
    gateway_id = dialog_manager.dialog_data["gateway_id"]
    gateway = await payment_gateway_service.get(gateway_id=gateway_id)

    if not gateway or not gateway.settings:
        return {}

    return {
        "id": gateway.id,
        "gateway_type": gateway.type,
        "is_active": gateway.is_active,
        "settings": gateway.settings.get_settings_as_list_data,
        "url": "t.me/remna_shop",
    }


@inject
async def field_getter(
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    **kwargs: Any,
) -> dict[str, Any]:
    gateway_id = dialog_manager.dialog_data["gateway_id"]
    selected_field = dialog_manager.dialog_data["selected_field"]

    gateway = await payment_gateway_service.get(gateway_id=gateway_id)

    if not gateway or not gateway.settings:
        return {}

    return {
        "gateway_type": gateway.type,
        "field": selected_field,
    }


@inject
async def currency_getter(
    dialog_manager: DialogManager,
    payment_gateway_service: FromDishka[PaymentGatewayService],
    **kwargs: Any,
) -> dict[str, Any]:
    default_currency = await payment_gateway_service.get_default_currency()

    return {
        "currency_list": [
            {
                "symbol": currency.symbol,
                "currency": currency.value,
                "enabled": currency == default_currency,
            }
            for currency in Currency
        ]
    }
