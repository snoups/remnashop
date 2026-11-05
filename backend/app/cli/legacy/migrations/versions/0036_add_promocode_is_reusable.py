from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UNIQUE_CONSTRAINT = "promocode_activations_promocode_id_user_id_key"


def upgrade() -> None:
    op.add_column(
        "promocodes",
        sa.Column(
            "is_reusable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Drop per-user uniqueness so reusable promocodes can be activated more than once
    # by the same user. Non-reusable promocodes are guarded in application logic.
    op.drop_constraint(_UNIQUE_CONSTRAINT, "promocode_activations", type_="unique")


def downgrade() -> None:
    # Reusable promocodes may have left duplicate (promocode_id, user_id) rows; keep the
    # earliest activation per pair before restoring the unique constraint.
    op.execute(
        """
        DELETE FROM promocode_activations a
        USING promocode_activations b
        WHERE a.promocode_id = b.promocode_id
          AND a.user_id = b.user_id
          AND a.id > b.id
        """
    )
    op.create_unique_constraint(
        _UNIQUE_CONSTRAINT,
        "promocode_activations",
        ["promocode_id", "user_id"],
    )
    op.drop_column("promocodes", "is_reusable")
