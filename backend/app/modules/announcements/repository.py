from datetime import datetime
from typing import Any, Final, Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.announcement import Announcement, AnnouncementView
from app.core.db.timestamp import NOW_FUNC
from app.modules.announcements.dto import AnnouncementDto, SlideDto
from app.modules.announcements.feed import REPO_RAW_BASE, FeedItem

_CONTENT_FIELDS: Final[frozenset[str]] = frozenset(
    {"icon", "severity", "title", "text", "url", "slides"}
)


def _row_values(item: FeedItem) -> dict[str, Any]:
    return {
        "notify_at": item.notify_at,
        "roles": item.roles,
        "versions": item.versions,
        "auto_open": item.auto_open,
        "content": item.model_dump(mode="json", include=set(_CONTENT_FIELDS)),
    }


def _to_dto(row: Announcement, seen_at: Optional[datetime]) -> AnnouncementDto:
    content = row.content
    return AnnouncementDto(
        id=row.id,
        icon=content["icon"],
        severity=content["severity"],
        title=content["title"],
        text=content["text"],
        url=content["url"],
        notify_at=row.notify_at,
        auto_open=row.auto_open,
        slides=[
            SlideDto(
                image_url=REPO_RAW_BASE + slide["image"] if slide["image"] else None,
                text=slide["text"],
                url=slide["url"],
            )
            for slide in content["slides"]
        ],
        roles=row.roles,
        versions=row.versions,
        seen_at=seen_at,
    )


class AnnouncementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_all(self, items: list[FeedItem]) -> None:
        await self.session.execute(
            delete(Announcement).where(Announcement.id.not_in([item.id for item in items]))
        )
        for item in items:
            values = _row_values(item)
            await self.session.execute(
                insert(Announcement)
                .values(id=item.id, **values)
                .on_conflict_do_update(
                    index_elements=["id"], set_={**values, "updated_at": NOW_FUNC}
                )
            )

    async def list_for_user(
        self, user_id: int, *, notify_from: datetime, now: datetime
    ) -> list[AnnouncementDto]:
        result = await self.session.execute(
            select(Announcement, AnnouncementView.seen_at)
            .outerjoin(
                AnnouncementView,
                and_(
                    AnnouncementView.announcement_id == Announcement.id,
                    AnnouncementView.user_id == user_id,
                ),
            )
            .where(Announcement.notify_at >= notify_from, Announcement.notify_at <= now)
            .order_by(Announcement.notify_at.desc(), Announcement.id)
        )
        return [_to_dto(row, seen_at) for row, seen_at in result.all()]

    async def mark_seen(self, user_id: int, ids: list[str], now: datetime) -> None:
        # an id removed from the feed between list and mark would break the FK
        existing = (
            await self.session.scalars(select(Announcement.id).where(Announcement.id.in_(ids)))
        ).all()
        if not existing:
            return
        await self.session.execute(
            insert(AnnouncementView)
            .values([{"user_id": user_id, "announcement_id": i, "seen_at": now} for i in existing])
            # first view starts the 24h window; a later one must not extend it
            .on_conflict_do_nothing(index_elements=["user_id", "announcement_id"])
        )
