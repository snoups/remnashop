from datetime import datetime, timedelta
from typing import Final, Optional

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from app.core.enums import Role
from app.modules.announcements.dto import AnnouncementDto

STALE_AFTER: Final[timedelta] = timedelta(hours=24)


def parse_panel_version(raw: str) -> Optional[Version]:
    try:
        return Version(raw)
    except InvalidVersion:
        return None


def is_visible(
    announcement: AnnouncementDto,
    *,
    role: Role,
    panel_version: Optional[Version],
    now: datetime,
) -> bool:
    if announcement.roles is not None and role.name not in announcement.roles:
        return False
    if announcement.seen_at is not None and now - announcement.seen_at >= STALE_AFTER:
        return False
    if announcement.versions is None:
        return True
    # a dev/fork build can't be placed in a range, so ranged items stay hidden
    if panel_version is None:
        return False
    return SpecifierSet(announcement.versions).contains(panel_version, prereleases=True)
