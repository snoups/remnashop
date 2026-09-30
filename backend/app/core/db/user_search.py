from typing import Final

from sqlalchemy import ColumnElement, or_

from app.core.constants import INT32_MAX
from app.core.db.models.user import User

_INT64_MAX: Final[int] = 2**63 - 1


def user_search_filter(search: str) -> ColumnElement[bool]:
    pattern = f"%{search}%"
    search_filters: list[ColumnElement[bool]] = [
        User.name.ilike(pattern),
        User.login.ilike(pattern),
        User.username.ilike(f"%{search.removeprefix('@')}%"),
        User.email.ilike(pattern),
    ]
    # a longer digit string is valid input but overflows the column type,
    # raising NumericValueOutOfRange from asyncpg
    if search.isdigit() and int(search) <= _INT64_MAX:
        search_filters.append(User.telegram_id == int(search))
    if search.isdigit() and int(search) <= INT32_MAX:
        search_filters.append(User.id == int(search))
    return or_(*search_filters)
