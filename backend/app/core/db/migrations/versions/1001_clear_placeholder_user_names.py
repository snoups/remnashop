import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "1001"
down_revision: Union[str, None] = "1000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_letter_or_digit(name: str) -> bool:
    return any(unicodedata.category(char)[0] in "LN" for char in name)


def upgrade() -> None:
    connection = op.get_bind()
    # placeholders written instead of a missing name: the telegram_id, the email's local part
    connection.execute(
        sa.text(
            "UPDATE users SET name = '' WHERE role = 'USER' AND ("
            "name = telegram_id::text"
            " OR (telegram_id IS NULL AND email IS NOT NULL AND name = split_part(email, '@', 1))"
            ")"
        )
    )
    # "." and emoji-only names; checked here, Postgres character classes follow the collation
    rows = connection.execute(
        sa.text("SELECT id, name FROM users WHERE role = 'USER' AND name <> ''")
    )
    blank_ids = [row.id for row in rows if not _has_letter_or_digit(row.name)]
    if blank_ids:
        connection.execute(
            sa.text("UPDATE users SET name = '' WHERE id = ANY(:ids)"), {"ids": blank_ids}
        )
    connection.execute(
        sa.text(
            "UPDATE users SET name = login WHERE role <> 'USER' AND name = '' AND login IS NOT NULL"
        )
    )


def downgrade() -> None:
    # the cleared placeholders are derivable, not lost data; nothing to restore
    pass
