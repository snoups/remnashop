from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest

from app.core.enums import Role
from app.modules.announcements.dto import AnnouncementDto
from app.modules.announcements.visibility import is_visible, parse_panel_version

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def _dto(**overrides: Any) -> AnnouncementDto:
    data: dict[str, Any] = {
        "id": "a",
        "icon": "info",
        "severity": "info",
        "title": {"en": "t"},
        "text": {},
        "url": None,
        "notify_at": NOW - timedelta(days=1),
        "auto_open": False,
        "slides": [],
        "roles": None,
        "versions": None,
    }
    data.update(overrides)
    return AnnouncementDto(**data)


def _visible(
    dto: AnnouncementDto, role: Role = Role.ADMIN, version: Optional[str] = "1.0.2"
) -> bool:
    panel = parse_panel_version(version) if version is not None else None
    return is_visible(dto, role=role, panel_version=panel, now=NOW)


def test_no_filters_is_visible_to_staff() -> None:
    assert _visible(_dto())


def test_roles_are_an_exact_list() -> None:
    owner_only = _dto(roles=["OWNER"])
    assert _visible(owner_only, role=Role.OWNER)
    assert not _visible(owner_only, role=Role.ADMIN)
    assert not _visible(_dto(roles=["ADMIN"]), role=Role.OWNER)


@pytest.mark.parametrize(
    ("spec", "version", "expected"),
    [
        (">=1.0.2", "1.0.2", True),
        (">=1.0.2", "v1.0.2", True),
        (">=1.0.2", "1.0.1", False),
        ("<1.0.3", "1.0.2-beta.1", True),
        (">=1.0.2", "1.0.2-beta.1", False),
        (">=1.0.0,<1.0.3", "1.0.3", False),
    ],
)
def test_versions_specifier(spec: str, version: str, expected: bool) -> None:
    assert _visible(_dto(versions=spec), version=version) is expected


def test_unparseable_panel_version_hides_only_versioned_items() -> None:
    assert parse_panel_version("dev") is None
    assert not _visible(_dto(versions=">=1.0.0"), version="dev")
    assert _visible(_dto(), version="dev")


def test_unseen_never_expires() -> None:
    assert _visible(_dto(notify_at=NOW - timedelta(days=400)))


def test_seen_stays_for_24_hours_then_hides() -> None:
    assert _visible(_dto(seen_at=NOW - timedelta(hours=23)))
    assert not _visible(_dto(seen_at=NOW - timedelta(hours=24)))
