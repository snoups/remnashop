from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ad_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("code", name="uq_ad_links_code"),
    )
    op.create_index("ix_ad_links_code", "ad_links", ["code"])
    op.create_index("ix_ad_links_name", "ad_links", ["name"])

    op.add_column(
        "users",
        sa.Column("ad_link_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_ad_link_id",
        "users",
        "ad_links",
        ["ad_link_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_ad_link_id", "users", ["ad_link_id"])


def downgrade() -> None:
    op.drop_index("ix_users_ad_link_id", table_name="users")
    op.drop_constraint("fk_users_ad_link_id", "users", type_="foreignkey")
    op.drop_column("users", "ad_link_id")
    op.drop_table("ad_links")
