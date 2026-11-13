from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Optional
from urllib.parse import urlparse

from remnapy import RemnawaveSDK
from remnapy.exceptions import ForbiddenError, UnauthorizedError

from app.cli.legacy.errors import LegacyMigrationError

_MIN_PANEL_MAJOR: Final[int] = 3
_PAGE_SIZE: Final[int] = 1000
_PANEL_OUTDATED: Final[str] = (
    "Remnawave panel 3.x is required: update the panel to 3.x first, then run the migration again"
)


@dataclass(frozen=True)
class PanelIndex:
    by_short_uuid: dict[str, int] = field(default_factory=dict)
    by_username: dict[str, int] = field(default_factory=dict)
    by_telegram_id: dict[int, list[int]] = field(default_factory=dict)
    first_connected_at: dict[int, datetime] = field(default_factory=dict)


async def fetch_panel_index(sdk: RemnawaveSDK, page_size: int = _PAGE_SIZE) -> PanelIndex:
    index = PanelIndex()
    cursor: Optional[int] = None
    while True:
        page = await sdk.users.get_users_stream(size=page_size, cursor=cursor)
        for user in page.users:
            index.by_short_uuid[user.short_uuid] = user.id
            index.by_username[user.username] = user.id
            if user.first_connected_at is not None:
                index.first_connected_at[user.id] = user.first_connected_at
            if user.telegram_id is not None:
                index.by_telegram_id.setdefault(user.telegram_id, []).append(user.id)
        if not page.has_more or page.next_cursor is None:
            return index
        cursor = int(page.next_cursor)


def resolve_panel_id(
    *, url: Optional[str], telegram_id: Optional[int], user_id: int, index: PanelIndex
) -> tuple[Optional[int], str]:
    segments = [part for part in urlparse(url or "").path.split("/") if part]
    if segments and (found := index.by_short_uuid.get(segments[-1])) is not None:
        return found, "shortUuid"

    username = f"rs_{telegram_id}" if telegram_id is not None else f"rs_web_{user_id}"
    if (found := index.by_username.get(username)) is not None:
        return found, "username"

    if telegram_id is not None:
        candidates = index.by_telegram_id.get(telegram_id, [])
        if len(candidates) == 1:
            return candidates[0], "telegramId"
        if len(candidates) > 1:
            return None, f"{len(candidates)} panel users share telegramId {telegram_id}"
    return None, "no matching panel user"


async def assert_panel_v3(sdk: RemnawaveSDK) -> None:
    try:
        metadata = await sdk.system.get_metadata()
        major = int(metadata.version.split(".")[0])
    except (UnauthorizedError, ForbiddenError) as error:
        raise LegacyMigrationError(
            f"Remnawave panel rejected the credentials: {error}. Check REMNAWAVE_TOKEN "
            "(Settings -> API Tokens in the panel) and, if the panel sits behind a protected "
            "proxy, REMNAWAVE_CADDY_TOKEN or REMNAWAVE_COOKIE"
        ) from error
    except Exception as error:
        raise LegacyMigrationError(
            f"Remnawave panel is unreachable or unreadable: {error}. {_PANEL_OUTDATED}"
        ) from error
    if major < _MIN_PANEL_MAJOR:
        raise LegacyMigrationError(f"Panel version {metadata.version}. {_PANEL_OUTDATED}")
