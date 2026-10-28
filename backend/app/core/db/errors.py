from typing import Optional

from sqlalchemy.exc import IntegrityError


def constraint_name(error: IntegrityError) -> Optional[str]:
    # error.orig is SQLAlchemy's asyncpg adapter exception; the driver's
    # exception, the one carrying .constraint_name, is its __cause__.
    # getattr because asyncpg ships no stubs for that attribute.
    driver_error = error.orig.__cause__ if error.orig is not None else None
    return getattr(driver_error, "constraint_name", None)
