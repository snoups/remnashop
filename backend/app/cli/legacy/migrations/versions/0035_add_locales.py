from typing import Sequence, Union

from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_LOCALES = ("BG", "DA", "EL", "FI", "HU", "NO", "SV", "TG", "TH", "ZH")


def upgrade() -> None:
    for locale in NEW_LOCALES:
        op.execute(f"ALTER TYPE locale ADD VALUE IF NOT EXISTS '{locale}'")


def downgrade() -> None:
    pass
