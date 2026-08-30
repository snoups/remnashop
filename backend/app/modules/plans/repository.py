from dataclasses import fields as dataclass_fields
from typing import Final

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.plan import Plan
from app.core.db.models.plan_duration import PlanDuration
from app.core.db.models.plan_price import PlanPrice
from app.core.enums import PlanAvailability
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    PlanDurationDto,
    PlanPriceDto,
    ReorderPlansDto,
    SetPlanDurationsDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)

# Arbitrary fixed keys for pg_advisory_xact_lock -- serialize concurrent writes that a
# plain read-then-write (or delete-then-insert) could otherwise interleave and corrupt.
_PLAN_ORDER_LOCK_KEY: Final[int] = 8221938
_PLAN_DURATIONS_LOCK_KEY: Final[int] = 8221939


class PlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _load_durations(self, plan_ids: list[int]) -> dict[int, list[PlanDurationDto]]:
        if not plan_ids:
            return {}

        duration_result = await self.session.execute(
            select(PlanDuration)
            .where(PlanDuration.plan_id.in_(plan_ids))
            .order_by(PlanDuration.order_index, PlanDuration.id)
        )
        duration_rows = duration_result.scalars().all()
        duration_ids = [row.id for row in duration_rows]

        prices_by_duration: dict[int, list[PlanPriceDto]] = {}
        if duration_ids:
            price_result = await self.session.execute(
                select(PlanPrice)
                .where(PlanPrice.plan_duration_id.in_(duration_ids))
                .order_by(PlanPrice.id)
            )
            for price_row in price_result.scalars():
                prices_by_duration.setdefault(price_row.plan_duration_id, []).append(
                    PlanPriceDto(currency=price_row.currency, price=price_row.price)
                )

        durations_by_plan: dict[int, list[PlanDurationDto]] = {}
        for row in duration_rows:
            durations_by_plan.setdefault(row.plan_id, []).append(
                PlanDurationDto(
                    days=row.days,
                    order_index=row.order_index,
                    prices=prices_by_duration.get(row.id, []),
                )
            )
        return durations_by_plan

    def _to_dto(self, row: Plan, durations: list[PlanDurationDto]) -> PlanDto:
        return PlanDto(
            id=row.id,
            public_code=row.public_code,
            name=row.name,
            description=row.description,
            tag=row.tag,
            type=row.type,
            availability=row.availability,
            traffic_limit_strategy=row.traffic_limit_strategy,
            traffic_limit=row.traffic_limit,
            device_limit=row.device_limit,
            allowed_telegram_ids=list(row.allowed_telegram_ids),
            allowed_emails=list(row.allowed_emails),
            internal_squads=list(row.internal_squads),
            external_squad=row.external_squad,
            order_index=row.order_index,
            is_active=row.is_active,
            is_trial=row.is_trial,
            durations=durations,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _list(self, *, active_only: bool) -> list[PlanDto]:
        query = select(Plan).order_by(Plan.order_index, Plan.id)
        if active_only:
            query = query.where(Plan.is_active.is_(True))

        result = await self.session.execute(query)
        rows = result.scalars().all()
        durations_by_plan = await self._load_durations([row.id for row in rows])
        return [self._to_dto(row, durations_by_plan.get(row.id, [])) for row in rows]

    async def list_all(self) -> list[PlanDto]:
        return await self._list(active_only=False)

    async def list_active(self) -> list[PlanDto]:
        return await self._list(active_only=True)

    async def _get_or_raise(self, plan_id: int) -> Plan:
        row = await self.session.get(Plan, plan_id)
        if row is None:
            raise NotFoundError(f"Plan '{plan_id}' not found")
        return row

    async def get_by_id(self, plan_id: int) -> PlanDto:
        row = await self._get_or_raise(plan_id)
        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def create(self, data: CreatePlanDto) -> PlanDto:
        await self.session.execute(select(func.pg_advisory_xact_lock(_PLAN_ORDER_LOCK_KEY)))
        count_result = await self.session.execute(select(func.count()).select_from(Plan))
        next_order_index = count_result.scalar_one()

        row = Plan(
            public_code=data.public_code,
            name=data.name,
            description=data.description,
            tag=data.tag,
            type=data.type,
            availability=PlanAvailability.ALL,
            traffic_limit_strategy=data.traffic_limit_strategy,
            traffic_limit=data.traffic_limit,
            device_limit=data.device_limit,
            allowed_telegram_ids=[],
            allowed_emails=[],
            internal_squads=[],
            external_squad=None,
            order_index=next_order_index,
            is_active=False,
            is_trial=data.is_trial,
        )
        self.session.add(row)

        try:
            await self.session.flush()
        except IntegrityError as error:
            constraint = getattr(error.orig, "constraint_name", None)
            if constraint == "ix_plans_public_code":
                raise ConflictError(
                    f"Plan with public_code '{data.public_code}' already exists"
                ) from error
            if constraint == "ix_plans_name":
                raise ConflictError(f"Plan with name '{data.name}' already exists") from error
            raise ConflictError("Plan could not be created due to a conflicting value") from error

        await self.session.refresh(row)
        return self._to_dto(row, [])

    async def update(self, data: UpdatePlanDto) -> PlanDto:
        row = await self._get_or_raise(data.plan_id)

        for field in dataclass_fields(data):
            if field.name == "plan_id":
                continue
            value = getattr(data, field.name)
            if value is not None:
                setattr(row, field.name, value)

        try:
            await self.session.flush()
        except IntegrityError as error:
            constraint = getattr(error.orig, "constraint_name", None)
            if constraint == "ix_plans_name":
                raise ConflictError(f"Plan name '{data.name}' already exists") from error
            raise ConflictError("Plan could not be updated due to a conflicting value") from error

        await self.session.refresh(row)
        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def delete(self, plan_id: int) -> None:
        await self._get_or_raise(plan_id)
        try:
            await self.session.execute(delete(Plan).where(Plan.id == plan_id))
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(f"Plan '{plan_id}' is still referenced by a promocode") from error

    async def set_durations(self, data: SetPlanDurationsDto) -> PlanDto:
        row = await self._get_or_raise(data.plan_id)

        seen_days: set[int] = set()
        for duration in data.durations:
            if duration.days in seen_days:
                raise ValidationError(f"Duplicate duration of {duration.days} days")
            seen_days.add(duration.days)

            currencies = [price.currency for price in duration.prices]
            if len(set(currencies)) != len(currencies):
                raise ValidationError(
                    f"Duplicate currency in prices for {duration.days}-day duration"
                )

        await self.session.execute(select(func.pg_advisory_xact_lock(_PLAN_DURATIONS_LOCK_KEY)))
        await self.session.execute(delete(PlanDuration).where(PlanDuration.plan_id == data.plan_id))
        await self.session.flush()

        duration_rows = [
            PlanDuration(plan_id=data.plan_id, days=duration.days, order_index=duration.order_index)
            for duration in data.durations
        ]
        self.session.add_all(duration_rows)
        await self.session.flush()

        self.session.add_all(
            PlanPrice(plan_duration_id=duration_row.id, currency=price.currency, price=price.price)
            for duration_row, duration in zip(duration_rows, data.durations)
            for price in duration.prices
        )
        await self.session.flush()
        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def update_access(self, data: UpdatePlanAccessDto) -> PlanDto:
        if (
            data.availability == PlanAvailability.ALLOWED
            and not data.allowed_telegram_ids
            and not data.allowed_emails
        ):
            raise ValidationError(
                "availability=ALLOWED requires at least one allowed telegram id or email"
            )

        row = await self._get_or_raise(data.plan_id)
        row.availability = data.availability
        row.allowed_telegram_ids = data.allowed_telegram_ids
        row.allowed_emails = data.allowed_emails

        await self.session.flush()
        await self.session.refresh(row)
        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def update_squads(self, data: UpdatePlanSquadsDto) -> PlanDto:
        row = await self._get_or_raise(data.plan_id)
        row.internal_squads = data.internal_squads
        row.external_squad = data.external_squad

        await self.session.flush()
        await self.session.refresh(row)
        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def reorder(self, data: ReorderPlansDto) -> list[PlanDto]:
        result = await self.session.execute(select(Plan))
        rows = {row.id: row for row in result.scalars()}

        if set(data.plan_ids) != set(rows) or len(data.plan_ids) != len(rows):
            raise ValidationError("Reorder must include every existing plan id exactly once")

        for index, plan_id in enumerate(data.plan_ids):
            rows[plan_id].order_index = index

        await self.session.flush()
        return await self.list_all()
