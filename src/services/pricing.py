from decimal import ROUND_DOWN, Decimal, InvalidOperation

from loguru import logger

from src.core.enums import Currency
from src.infrastructure.database.models.dto import PriceDetailsDto, UserDto

from .base import BaseService


class PricingService(BaseService):
    def calculate(self, user: UserDto, price: Decimal, currency: Currency) -> PriceDetailsDto:
        logger.debug(
            f"Calculating price for amount '{price}' and currency "
            f"'{currency}' for user '{user.telegram_id}'"
        )

        if price <= 0:
            logger.debug(f"Price is zero, returning without discount")
            return PriceDetailsDto(
                original_amount=Decimal(0),
                final_amount=Decimal(0),
            )

        discount_percent = min(user.purchase_discount or user.personal_discount or 0, 100)

        if discount_percent >= 100:
            logger.info(f"100% discount applied, price is free for user '{user.telegram_id}'")
            return PriceDetailsDto(
                original_amount=price,
                discount_percent=100,
                final_amount=Decimal(0),
            )

        discounted = price * (Decimal(100) - Decimal(discount_percent)) / Decimal(100)
        final_amount = self.apply_currency_rules(discounted, currency)

        if final_amount == price:
            discount_percent = 0

        logger.info(
            f"Price calculated: original='{price}', "
            f"discount_percent='{discount_percent}', final='{final_amount}'"
        )

        return PriceDetailsDto(
            original_amount=price,
            discount_percent=discount_percent,
            final_amount=final_amount,
        )

    def parse_price(self, input_price: str, currency: Currency) -> Decimal:
        logger.debug(f"Parsing input price '{input_price}' for currency '{currency}'")
        try:
            price = Decimal(input_price.strip())
        except InvalidOperation:
            raise ValueError(f"Invalid numeric format provided for price: '{input_price}'")

        if price < 0:
            raise ValueError(f"Negative price provided: '{input_price}'")
        if price == 0:
            return Decimal(0)

        final_price = self.apply_currency_rules(price, currency)
        logger.debug(f"Parsed price '{final_price}' after applying currency rules")
        return final_price

    def apply_currency_rules(self, amount: Decimal, currency: Currency) -> Decimal:
        logger.debug(f"Applying currency rules for amount '{amount}' and currency '{currency}'")

        match currency:
            case Currency.XTR | Currency.RUB:
                amount = amount.to_integral_value(rounding=ROUND_DOWN)
                min_amount = Decimal(1)
            case _:
                amount = amount.quantize(Decimal("0.01"))
                min_amount = Decimal("0.01")

        if amount < min_amount:
            logger.debug(f"Amount '{amount}' less than min '{min_amount}', adjusting")
            amount = min_amount

        logger.debug(f"Final amount after currency rules: '{amount}'")
        return amount
