from datetime import date, datetime
from typing import Optional

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.errors import constraint_name
from app.core.db.filters import in_ids
from app.core.db.models.ad_link import AdLink
from app.core.db.models.ad_link_attribution import AdLinkAttribution
from app.core.db.models.user import User
from app.core.db.partial_update import apply_partial_update
from app.core.enums import AdLinkChannel, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.advertising.dto import (
    AdLinkAttributionDto,
    AdLinkDto,
    CreateAdLinkDto,
    DailyAttributionCountDto,
    UpdateAdLinkDto,
    UserAdAttributionDto,
)


def _in_range(
    created_from: Optional[datetime], created_to: Optional[datetime]
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if created_from is not None:
        filters.append(AdLinkAttribution.created_at >= created_from)
    if created_to is not None:
        filters.append(AdLinkAttribution.created_at < created_to)
    return filters


def _ensure_some_channel(row: AdLink) -> None:
    if not row.allow_bot and not row.allow_webcabinet:
        raise ValidationError(
            "AdLink must allow at least one channel", code=ErrorCode.AD_LINK_NO_CHANNEL
        )


class AdLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: AdLink) -> AdLinkDto:
        return AdLinkDto.model_validate(row, from_attributes=True)

    def _to_attribution_dto(self, row: AdLinkAttribution) -> AdLinkAttributionDto:
        return AdLinkAttributionDto.model_validate(row, from_attributes=True)

    async def _get_or_raise(self, ad_link_id: int) -> AdLink:
        row = await self.session.get(AdLink, ad_link_id)
        if row is None:
            raise NotFoundError(
                f"AdLink '{ad_link_id}' not found", code=ErrorCode.AD_LINK_NOT_FOUND
            )
        return row

    async def get_by_id(self, ad_link_id: int) -> AdLinkDto:
        return self._to_dto(await self._get_or_raise(ad_link_id))

    async def find_by_code(self, code: str) -> Optional[AdLinkDto]:
        row = await self.session.scalar(select(AdLink).where(AdLink.code == code))
        return self._to_dto(row) if row is not None else None

    async def list_paginated(
        self, *, is_active: Optional[bool] = None, page: int = 1, page_size: int = 50
    ) -> tuple[list[AdLinkDto], int]:
        filters = [AdLink.is_active == is_active] if is_active is not None else []

        total = await self.session.scalar(select(func.count()).select_from(AdLink).where(*filters))

        stmt = (
            select(AdLink)
            .where(*filters)
            .order_by(AdLink.is_active.desc(), AdLink.created_at.desc(), AdLink.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self._to_dto(row) for row in rows], int(total or 0)

    async def create(self, data: CreateAdLinkDto) -> AdLinkDto:
        row = AdLink(
            name=data.name,
            code=data.code,
            cost=data.cost,
            cost_currency=data.cost_currency,
            revenue_share_percent=data.revenue_share_percent,
            allow_bot=data.allow_bot,
            allow_webcabinet=data.allow_webcabinet,
            note=data.note,
            created_by=data.created_by,
        )
        _ensure_some_channel(row)
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as error:
            if constraint_name(error) != "ix_ad_links_code":
                raise
            raise ConflictError(
                f"AdLink with code '{data.code}' already exists", code=ErrorCode.AD_LINK_CODE_TAKEN
            ) from error
        await self.session.refresh(row)
        return self._to_dto(row)

    async def update(self, data: UpdateAdLinkDto) -> AdLinkDto:
        row = await self._get_or_raise(data.ad_link_id)
        apply_partial_update(row, data, skip=frozenset({"ad_link_id", "note"}))
        if data.note is not None:
            # "" clears it: None already means "leave unchanged"
            row.note = data.note or None
        _ensure_some_channel(row)
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def delete_if_no_attributions(self, ad_link_id: int) -> None:
        # a concurrent attribution INSERT takes FOR KEY SHARE on this row, so it
        # waits for this transaction instead of racing the count-then-delete
        locked = await self.session.execute(
            select(AdLink).where(AdLink.id == ad_link_id).with_for_update()
        )
        try:
            row = locked.scalar_one()
        except NoResultFound as error:
            raise NotFoundError(
                f"AdLink '{ad_link_id}' not found", code=ErrorCode.AD_LINK_NOT_FOUND
            ) from error

        if await self.count_attributions(ad_link_id) > 0:
            raise ConflictError(
                f"AdLink '{ad_link_id}' has attributions and cannot be deleted -- "
                "deactivate it instead",
                code=ErrorCode.AD_LINK_HAS_ATTRIBUTIONS,
            )

        await self.session.delete(row)
        await self.session.flush()

    async def list_user_links(self, user_ids: list[int]) -> list[tuple[int, int, str]]:
        result: list[tuple[int, int, str]] = []
        stmt = (
            select(AdLinkAttribution.user_id, AdLink.id, AdLink.name)
            .join(AdLink, AdLink.id == AdLinkAttribution.ad_link_id)
            .where(in_ids(AdLinkAttribution.user_id, user_ids))
        )
        result.extend((await self.session.execute(stmt)).tuples().all())
        return result

    async def create_attribution(
        self, *, ad_link_id: int, user_id: int, channel: AdLinkChannel
    ) -> AdLinkAttributionDto:
        row = AdLinkAttribution(ad_link_id=ad_link_id, user_id=user_id, channel=channel)
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as error:
            if constraint_name(error) != "ux_ad_link_attributions_user_id":
                raise
            raise ConflictError(
                f"User '{user_id}' is already attributed to an ad link",
                code=ErrorCode.USER_ALREADY_ATTRIBUTED,
            ) from error
        await self.session.refresh(row)
        return self._to_attribution_dto(row)

    async def list_all(self, *, is_active: Optional[bool] = None) -> list[AdLinkDto]:
        filters = [AdLink.is_active == is_active] if is_active is not None else []
        rows = (await self.session.scalars(select(AdLink).where(*filters))).all()
        return [self._to_dto(row) for row in rows]

    async def count_attributions(
        self,
        ad_link_id: int,
        *,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(AdLinkAttribution)
            .where(AdLinkAttribution.ad_link_id == ad_link_id, *_in_range(created_from, created_to))
        )
        return int(await self.session.scalar(stmt) or 0)

    async def count_attributions_by_channel(
        self,
        ad_link_id: int,
        *,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
    ) -> dict[AdLinkChannel, int]:
        stmt = (
            select(AdLinkAttribution.channel, func.count())
            .where(AdLinkAttribution.ad_link_id == ad_link_id, *_in_range(created_from, created_to))
            .group_by(AdLinkAttribution.channel)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return dict(rows.all())

    async def list_attributed_user_ids(
        self,
        ad_link_id: int,
        *,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
    ) -> list[int]:
        stmt = select(AdLinkAttribution.user_id).where(
            AdLinkAttribution.ad_link_id == ad_link_id, *_in_range(created_from, created_to)
        )
        return list((await self.session.scalars(stmt)).all())

    async def list_attributions(
        self,
        ad_link_ids: list[int],
        *,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
    ) -> list[tuple[int, int, AdLinkChannel]]:
        # (ad_link_id, user_id, channel), one row per attributed user
        if not ad_link_ids:
            return []
        stmt = select(
            AdLinkAttribution.ad_link_id, AdLinkAttribution.user_id, AdLinkAttribution.channel
        ).where(
            in_ids(AdLinkAttribution.ad_link_id, ad_link_ids), *_in_range(created_from, created_to)
        )
        return list((await self.session.execute(stmt)).tuples().all())

    async def daily_attribution_counts(
        self,
        ad_link_id: int,
        *,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
    ) -> list[DailyAttributionCountDto]:
        day_col = func.date(func.timezone("UTC", AdLinkAttribution.created_at))
        stmt = (
            select(day_col, AdLinkAttribution.channel, func.count())
            .where(AdLinkAttribution.ad_link_id == ad_link_id, *_in_range(created_from, created_to))
            .group_by(day_col, AdLinkAttribution.channel)
            .order_by(day_col)
        )
        days: dict[date, DailyAttributionCountDto] = {}
        for day, channel, count in (await self.session.execute(stmt)).tuples():
            entry = days.setdefault(day, DailyAttributionCountDto(day=day, count=0))
            entry.count += count
            entry.by_channel[channel] = count
        return list(days.values())

    async def list_attributions_paginated(
        self,
        ad_link_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
        hide_staff_from: Optional[int] = None,
    ) -> tuple[list[AdLinkAttributionDto], int]:
        condition: ColumnElement[bool] = AdLinkAttribution.ad_link_id == ad_link_id
        if hide_staff_from is not None:
            # same rule as visible_user: staff rows are hidden, the viewer's own is not
            condition = and_(
                condition,
                or_(
                    AdLinkAttribution.user_id.in_(select(User.id).where(User.role == Role.USER)),
                    AdLinkAttribution.user_id == hide_staff_from,
                ),
            )
        total = await self.session.scalar(
            select(func.count()).select_from(AdLinkAttribution).where(condition)
        )
        stmt = (
            select(AdLinkAttribution)
            .where(condition)
            .order_by(AdLinkAttribution.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self._to_attribution_dto(row) for row in rows], int(total or 0)

    async def find_user_attribution(self, user_id: int) -> Optional[UserAdAttributionDto]:
        row = (
            await self.session.execute(
                select(AdLinkAttribution, AdLink)
                .join(AdLink, AdLink.id == AdLinkAttribution.ad_link_id)
                .where(AdLinkAttribution.user_id == user_id)
            )
        ).first()
        if row is None:
            return None
        attribution, ad_link = row._tuple()
        return UserAdAttributionDto(
            ad_link_id=ad_link.id,
            name=ad_link.name,
            code=ad_link.code,
            channel=attribution.channel,
            attributed_at=attribution.created_at,
        )
