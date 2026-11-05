from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE access_mode_new AS ENUM (
            'PUBLIC',
            'INVITED',
            'PURCHASE_BLOCKED',
            'REG_BLOCKED',
            'RESTRICTED'
        );
        """
    )

    op.execute(
        """
        ALTER TABLE settings
        ALTER COLUMN access_mode
        TYPE text
        USING access_mode::text;
        """
    )

    op.execute(
        """
        UPDATE settings
        SET access_mode = CASE access_mode
            WHEN 'ALL' THEN 'PUBLIC'
            WHEN 'PURCHASE' THEN 'PURCHASE_BLOCKED'
            WHEN 'BLOCKED' THEN 'RESTRICTED'
            ELSE access_mode
        END
        WHERE access_mode IS NOT NULL;
        """
    )

    op.execute(
        """
        ALTER TABLE settings
        ALTER COLUMN access_mode
        DROP DEFAULT,
        ALTER COLUMN access_mode
        TYPE access_mode_new
        USING access_mode::text::access_mode_new,
        ALTER COLUMN access_mode
        SET DEFAULT 'PUBLIC';
        """
    )

    op.execute("DROP TYPE access_mode;")

    op.execute("ALTER TYPE access_mode_new RENAME TO access_mode;")


def downgrade() -> None:
    op.execute("ALTER TYPE access_mode RENAME TO access_mode_new;")

    op.execute("""
        CREATE TYPE access_mode AS ENUM (
            'ALL',
            'INVITED',
            'PURCHASE',
            'BLOCKED'
        )
    """)

    op.execute(
        """
        ALTER TABLE settings
        ALTER COLUMN access_mode
        TYPE text
        USING access_mode::text;
        """
    )

    op.execute(
        """
        UPDATE settings
        SET access_mode = CASE access_mode
            WHEN 'PUBLIC' THEN 'ALL'
            WHEN 'RESTRICTED' THEN 'BLOCKED'
            WHEN 'PURCHASE_BLOCKED' THEN 'PURCHASE'
            ELSE access_mode
        END
        WHERE access_mode IS NOT NULL;
        """
    )

    op.execute(
        """
        ALTER TABLE settings
        ALTER COLUMN access_mode
        DROP DEFAULT,
        ALTER COLUMN access_mode
        TYPE access_mode
        USING access_mode::text::access_mode,
        ALTER COLUMN access_mode
        SET DEFAULT 'ALL';
        """
    )

    op.execute("DROP TYPE access_mode_new;")
