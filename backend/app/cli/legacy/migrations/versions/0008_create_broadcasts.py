from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broadcasts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PROCESSING",
                "COMPLETED",
                "CANCELED",
                "DELETED",
                "ERROR",
                name="broadcast_status",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "audience",
            sa.Enum(
                "ALL",
                "PLAN",
                "SUBSCRIBED",
                "UNSUBSCRIBED",
                "EXPIRED",
                "TRIAL",
                name="broadcast_audience",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_table(
        "broadcast_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("broadcast_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "SENT",
                "FAILED",
                "EDITED",
                "DELETED",
                "PENDING",
                name="broadcast_message_status",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["broadcast_id"],
            ["broadcasts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("broadcast_messages")
    op.drop_table("broadcasts")
