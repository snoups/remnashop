from dataclasses import fields
from typing import Any, Final

_EMPTY_SKIP: Final[frozenset[str]] = frozenset()


def apply_partial_update(row: Any, data: Any, *, skip: frozenset[str] = _EMPTY_SKIP) -> None:
    """Copy every set (non-None) field of an Update-DTO onto an ORM row: PATCH
    semantics shared by the update() methods that would otherwise each spell out
    a dozen `if data.x is not None: row.x = data.x` lines (and trip C901).

    field access is reflective here; None can't be written back through
    a PATCH. `skip` excludes identity fields (plan_id, promocode_id, ...).
    """
    for field in fields(data):
        if field.name in skip:
            continue
        value = getattr(data, field.name)
        if value is not None:
            setattr(row, field.name, value)
