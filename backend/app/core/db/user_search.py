from sqlalchemy import ColumnElement, or_

from app.core.constants import INT32_MAX, INT64_MAX
from app.core.db.models.user import User


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def user_search_filter(search: str, *, include_login: bool = True) -> ColumnElement[bool]:
    # include_login=False where the response never shows the login: filtering
    # on a field the caller can't read is an oracle for it
    pattern = f"%{_escape_like(search)}%"
    username_pattern = f"%{_escape_like(search.removeprefix('@'))}%"
    search_filters: list[ColumnElement[bool]] = [
        User.name.ilike(pattern, escape="\\"),
        User.username.ilike(username_pattern, escape="\\"),
        User.email.ilike(pattern, escape="\\"),
    ]
    if include_login:
        search_filters.append(User.login.ilike(pattern, escape="\\"))
    # a longer digit string is valid input but overflows the column type,
    # raising NumericValueOutOfRange from asyncpg
    if search.isascii() and search.isdigit() and int(search) <= INT64_MAX:
        search_filters.append(User.telegram_id == int(search))
    if search.isascii() and search.isdigit() and int(search) <= INT32_MAX:
        search_filters.append(User.id == int(search))
    return or_(*search_filters)
