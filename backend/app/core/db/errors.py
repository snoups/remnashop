from typing import Optional

from sqlalchemy.exc import IntegrityError


def constraint_name(error: IntegrityError) -> Optional[str]:
    # asyncpg's exception carries .constraint_name but no stub declares
    # it, and SQLAlchemy types .orig as a bare BaseException -- getattr is the
    # ceiling until asyncpg ships types. Confined here so call sites stay clean.
    return getattr(error.orig, "constraint_name", None)
