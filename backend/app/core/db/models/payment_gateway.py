from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base import BaseSql
from app.core.db.encrypted_string import EncryptedString
from app.core.db.timestamp import TimestampMixin
from app.core.enums import PaymentGatewayType


class PaymentGateway(BaseSql, TimestampMixin):
    __tablename__ = "payment_gateways"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[PaymentGatewayType] = mapped_column(unique=True)
    order_index: Mapped[int] = mapped_column(default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(default=False, server_default="false")

    # JSON dict[str, str] encrypted as one blob: the field set differs per type
    # (modules/gateways/field_catalog.py) and the admin form saves it whole
    settings: Mapped[Optional[str]] = mapped_column(EncryptedString())
