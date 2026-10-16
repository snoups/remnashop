from typing import Any, Optional

import pytest

from app.modules.event_log.usecases.process_outbox_entry import _target_id


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"target": {"id": 9}, "user": {"id": 7}}, 9),
        ({"user": {"id": 7}}, 7),
        ({"user_id": 3}, 3),
        ({"user": {"id": 0}, "target": None}, None),
        ({"user_id": 0}, None),
        ({"actor": {"id": 5}}, None),
        ({}, None),
    ],
)
def test_target_id_resolves_the_subject(payload: dict[str, Any], expected: Optional[int]) -> None:
    assert _target_id(payload) == expected
