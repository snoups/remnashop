from dataclasses import dataclass
from typing import Optional

from app.core.db.partial_update import apply_partial_update


@dataclass
class _UpdateDto:
    entity_id: int
    name: Optional[str] = None
    count: Optional[int] = None


class _Row:
    def __init__(self) -> None:
        self.name = "old"
        self.count = 1


def test_applies_only_set_fields_and_skips_identity() -> None:
    row = _Row()

    apply_partial_update(row, _UpdateDto(entity_id=5, name="new"), skip=frozenset({"entity_id"}))

    assert row.name == "new"
    assert row.count == 1  # left untouched: None means "leave unchanged"
    assert not hasattr(row, "entity_id")  # skipped, not copied


def test_none_cannot_clear_a_field() -> None:
    row = _Row()

    apply_partial_update(row, _UpdateDto(entity_id=5, count=None), skip=frozenset({"entity_id"}))

    assert row.count == 1
