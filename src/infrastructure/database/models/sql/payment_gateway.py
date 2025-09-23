from typing import Optional

from sqlalchemy import JSON, Boolean, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.core.enums import Currency, PaymentGatewayType

from .base import BaseSql


class PaymentGateway(BaseSql):
    __tablename__ = "payment_gateways"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    type: Mapped[PaymentGatewayType] = mapped_column(
        Enum(PaymentGatewayType),
        nullable=False,
        unique=True,
    )

    currency: Mapped[Currency] = mapped_column(Enum(Currency), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
