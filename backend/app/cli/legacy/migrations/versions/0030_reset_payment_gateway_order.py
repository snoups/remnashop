from typing import Sequence, Union

from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORDER = [
    "TELEGRAM_STARS",
    "YOOKASSA",
    "YOOMONEY",
    "VALUTIX",
    "CRYPTOMUS",
    "HELEKET",
    "CRYPTOPAY",
    "FREEKASSA",
    "MULENPAY",
    "PAYMASTER",
    "PLATEGA",
    "ROBOKASSA",
    "URLPAY",
    "WATA",
]


def upgrade() -> None:
    for index, gateway_type in enumerate(_ORDER, start=1):
        op.execute(
            f"UPDATE payment_gateways SET order_index = {index} WHERE type = '{gateway_type}'"
        )


def downgrade() -> None:
    pass
