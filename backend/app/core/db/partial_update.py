from dataclasses import fields
from typing import Any, Final

_EMPTY_SKIP: Final[frozenset[str]] = frozenset()


def apply_partial_update(row: Any, data: Any, *, skip: frozenset[str] = _EMPTY_SKIP) -> None:
    """Copy every non-None field of an Update-DTO onto an ORM row (PATCH
    semantics: None can't be written back this way). `skip` excludes identity
    fields such as plan_id."""
    for field in fields(data):
        if field.name in skip:
            continue
        value = getattr(data, field.name)
        if value is not None:
            setattr(row, field.name, value)
