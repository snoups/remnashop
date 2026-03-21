import hashlib
import string
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base62_encode(number: int) -> str:
    alphabet = string.ascii_letters + string.digits

    if number == 0:
        return alphabet[0]

    arr = []
    base = len(alphabet)

    while number:
        number, rem = divmod(number, base)
        arr.append(alphabet[rem])

    arr.reverse()
    return "".join(arr)


def _generate_ref_code(telegram_id: int, secret: str, length: int = 6) -> str:
    data = f"{telegram_id}:{secret}".encode("utf-8")
    digest = hashlib.sha256(data).digest()
    code_int = int.from_bytes(digest[:6], "big")
    code = _base62_encode(code_int)
    return code[:length].rjust(length, "0")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "referral_code",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "users", sa.Column("points", sa.Integer(), nullable=False, server_default=sa.text("0"))
    )

    conn = op.get_bind()
    ctx = context.get_context()
    crypt_key = ctx.opts["crypt_key"]
    users = conn.execute(sa.text("SELECT id, telegram_id FROM users")).fetchall()

    for user_id, telegram_id in users:
        code = _generate_ref_code(telegram_id, crypt_key)
        conn.execute(
            sa.text("UPDATE users SET referral_code = :code WHERE id = :id"),
            {"code": code, "id": user_id},
        )

    op.create_unique_constraint("uq_users_referral_code", "users", ["referral_code"])
    op.alter_column("users", "referral_code", server_default=None)

    referral_level_enum = sa.Enum(
        "FIRST",
        "SECOND",
        name="referral_level",
    )
    referral_reward_type_enum = sa.Enum(
        "POINTS",
        "EXTRA_DAYS",
        name="referral_reward_type",
    )

    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("referrer_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("referred_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("level", referral_level_enum, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["referred_telegram_id"], ["users.telegram_id"]),
        sa.ForeignKeyConstraint(["referrer_telegram_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("referral_id", sa.Integer(), nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("type", referral_reward_type_enum, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("is_issued", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["referral_id"], ["referrals.id"]),
        sa.ForeignKeyConstraint(["user_telegram_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "settings",
        sa.Column(
            "referral",
            sa.JSON(),
            nullable=False,
            server_default=(
                '{"enable": true, '
                '"level": 1, '
                '"accrual_strategy": "ON_FIRST_PAYMENT", '
                '"reward": {'
                '"type": "EXTRA_DAYS", '
                '"strategy": "AMOUNT", '
                '"config": {"1": 5}'
                "}}"
            ),
        ),
    )
    op.alter_column(
        "settings",
        "user_notifications",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=False,
    )
    op.alter_column(
        "settings",
        "system_notifications",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=False,
    )

    new_gateways = [
        "CRYPTOPAY",
        "ROBOKASSA",
        "WATAPAY",
        "FREEKASSA",
        "TRIBUTE",
        "MULENPAY",
        "KASSAI",
    ]

    for gateway in new_gateways:
        op.execute(f"ALTER TYPE payment_gateway_type ADD VALUE IF NOT EXISTS '{gateway}'")


def downgrade() -> None:
    op.drop_table("referral_rewards")
    op.drop_table("referrals")
    op.drop_column("settings", "referral")
    op.alter_column(
        "settings",
        "system_notifications",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=True,
    )
    op.alter_column(
        "settings",
        "user_notifications",
        existing_type=postgresql.JSON(astext_type=sa.Text()),
        nullable=True,
    )
    op.drop_constraint("uq_users_referral_code", "users", type_="unique")
    op.drop_column("users", "referral_code")
    op.drop_column("users", "points")
