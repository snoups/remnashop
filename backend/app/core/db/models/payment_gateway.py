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

    # JSON-serialized dict[str, str], encrypted as one opaque blob -- the
    # field set is polymorphic per type (see modules/gateways/field_catalog.py),
    # always read/written as one bundle through the admin form.
    settings: Mapped[Optional[str]] = mapped_column(EncryptedString())
