from datetime import date
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.ad_link import AdLink
from app.core.db.models.ad_link_attribution import AdLinkAttribution
from app.core.db.partial_update import apply_partial_update
from app.core.enums import AdLinkChannel
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.advertising.dto import (
    AdLinkAttributionDto,
    AdLinkDto,
    CreateAdLinkDto,
    UpdateAdLinkDto,
)


class AdLinkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: AdLink) -> AdLinkDto:
        return AdLinkDto(
            id=row.id,
            name=row.name,
            code=row.code,
            cost=row.cost,
            cost_currency=row.cost_currency,
            is_active=row.is_active,
            note=row.note,
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _attribution_to_dto(self, row: AdLinkAttribution) -> AdLinkAttributionDto:
        return AdLinkAttributionDto(
            id=row.id,
            ad_link_id=row.ad_link_id,
            user_id=row.user_id,
            channel=row.channel,
            created_at=row.created_at,
        )

    async def _get_or_raise(self, ad_link_id: int) -> AdLink:
        row = await self.session.get(AdLink, ad_link_id)
        if row is None:
            raise NotFoundError(f"AdLink '{ad_link_id}' not found")
        return row

    async def get_by_id(self, ad_link_id: int) -> AdLinkDto:
        return self._to_dto(await self._get_or_raise(ad_link_id))

    async def get_by_code(self, code: str) -> Optional[AdLinkDto]:
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
            .order_by(AdLink.created_at.desc())
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
            note=data.note,
            created_by=data.created_by,
        )
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(f"AdLink with code '{data.code}' already exists") from error
        await self.session.refresh(row)
        return self._to_dto(row)

    async def update(self, data: UpdateAdLinkDto) -> AdLinkDto:
        row = await self._get_or_raise(data.ad_link_id)
        apply_partial_update(row, data, skip=frozenset({"ad_link_id"}))
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def delete_if_no_attributions(self, ad_link_id: int) -> None:
        # Lock the ad_link row before counting attributions: Postgres takes an
        # implicit FOR KEY SHARE lock on it for any concurrent
        # create_attribution INSERT (FK reference), so that insert blocks
        # until this transaction commits/rolls back instead of racing the
        # count-then-delete below (was a TOCTOU -- see PromocodeRepository's
        # claim_activation for the same pattern).
        locked = await self.session.execute(
            select(AdLink).where(AdLink.id == ad_link_id).with_for_update()
        )
        try:
            row = locked.scalar_one()
        except NoResultFound as error:
            raise NotFoundError(f"AdLink '{ad_link_id}' not found") from error

        if await self.count_attributions(ad_link_id) > 0:
            raise ValidationError(
                f"AdLink '{ad_link_id}' has attributions and cannot be deleted -- "
                "deactivate it instead"
            )

        await self.session.delete(row)
        await self.session.flush()

    async def create_attribution(
        self, *, ad_link_id: int, user_id: int, channel: AdLinkChannel
    ) -> AdLinkAttributionDto:
        row = AdLinkAttribution(ad_link_id=ad_link_id, user_id=user_id, channel=channel)
        self.session.add(row)
        try:
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(f"User '{user_id}' is already attributed to an ad link") from error
        await self.session.refresh(row)
        return self._attribution_to_dto(row)

    async def count_attributions(self, ad_link_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(AdLinkAttribution)
            .where(AdLinkAttribution.ad_link_id == ad_link_id)
        )
        return int(await self.session.scalar(stmt) or 0)

    async def count_attributions_by_channel(self, ad_link_id: int) -> dict[AdLinkChannel, int]:
        stmt = (
            select(AdLinkAttribution.channel, func.count())
            .where(AdLinkAttribution.ad_link_id == ad_link_id)
            .group_by(AdLinkAttribution.channel)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return dict(rows.all())

    async def list_attributed_user_ids(self, ad_link_id: int) -> list[int]:
        stmt = select(AdLinkAttribution.user_id).where(AdLinkAttribution.ad_link_id == ad_link_id)
        return list((await self.session.scalars(stmt)).all())

    async def daily_attribution_counts(self, ad_link_id: int) -> list[tuple[date, int]]:
        day_col = func.date(func.timezone("UTC", AdLinkAttribution.created_at))
        stmt = (
            select(day_col, func.count())
            .where(AdLinkAttribution.ad_link_id == ad_link_id)
            .group_by(day_col)
            .order_by(day_col)
        )
        rows = (await self.session.execute(stmt)).tuples()
        return list(rows.all())

    async def list_attributions_paginated(
        self, ad_link_id: int, *, page: int = 1, page_size: int = 50
    ) -> tuple[list[AdLinkAttributionDto], int]:
        total = await self.session.scalar(
            select(func.count())
            .select_from(AdLinkAttribution)
            .where(AdLinkAttribution.ad_link_id == ad_link_id)
        )
        stmt = (
            select(AdLinkAttribution)
            .where(AdLinkAttribution.ad_link_id == ad_link_id)
            .order_by(AdLinkAttribution.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.scalars(stmt)).all()
        return [self._attribution_to_dto(row) for row in rows], int(total or 0)
