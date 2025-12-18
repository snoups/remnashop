from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE access_mode_new AS ENUM (
            'PUBLIC',
            'INVITED',
            'RESTRICTED'
        );
    """)

    op.execute("""
        ALTER TABLE settings
        ALTER COLUMN access_mode
        TYPE text
        USING access_mode::text;
    """)

    op.execute("""
        UPDATE settings
        SET access_mode = CASE access_mode
            WHEN 'PURCHASE_BLOCKED' THEN 'PUBLIC'
            WHEN 'REG_BLOCKED' THEN 'PUBLIC'
            ELSE access_mode
        END;
    """)

    op.execute("""
        ALTER TABLE settings
        ALTER COLUMN access_mode DROP DEFAULT,
        ALTER COLUMN access_mode
        TYPE access_mode_new
        USING access_mode::text::access_mode_new,
        ALTER COLUMN access_mode
        SET DEFAULT 'PUBLIC';
    """)

    op.execute("DROP TYPE access_mode;")
    op.execute("ALTER TYPE access_mode_new RENAME TO access_mode;")

    op.add_column(
        "settings",
        sa.Column(
            "purchases_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    op.add_column(
        "settings",
        sa.Column(
            "registration_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.execute("""
        CREATE TYPE access_mode_old AS ENUM (
            'PUBLIC',
            'INVITED',
            'PURCHASE_BLOCKED',
            'REG_BLOCKED',
            'RESTRICTED'
        );
    """)

    op.execute("""
        ALTER TABLE settings
        ALTER COLUMN access_mode
        TYPE text
        USING access_mode::text;
    """)

    op.execute("""
        UPDATE settings
        SET access_mode = access_mode;
    """)

    op.execute("""
        ALTER TABLE settings
        ALTER COLUMN access_mode DROP DEFAULT,
        ALTER COLUMN access_mode
        TYPE access_mode_old
        USING access_mode::text::access_mode_old,
        ALTER COLUMN access_mode
        SET DEFAULT 'PUBLIC';
    """)

    op.execute("DROP TYPE access_mode;")
    op.execute("ALTER TYPE access_mode_old RENAME TO access_mode;")

    op.drop_column("settings", "registration_allowed")
    op.drop_column("settings", "purchases_allowed")
