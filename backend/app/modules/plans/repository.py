from decimal import Decimal
from typing import Final, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.errors import constraint_name
from app.core.db.models.plan import Plan
from app.core.db.models.plan_duration import PlanDuration
from app.core.db.models.plan_price_override import PlanPriceOverride
from app.core.db.partial_update import apply_partial_update
from app.core.enums import Currency, PlanAvailability, PlanBadge, PlanType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    PlanDurationDto,
    PlanPriceOverrideDto,
    ReorderPlansDto,
    SetPlanDurationBasePriceDto,
    SetPlanDurationsDto,
    SetPlanPriceOverrideDto,
    UpdatePlanAccessDto,
    UpdatePlanDiscountDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)

# Fixed pg_advisory_xact_lock keys that serialize writes a read-then-write (or
# delete-then-insert) would otherwise interleave.
_PLAN_ORDER_LOCK_KEY: Final[int] = 8221938
_PLAN_DURATIONS_LOCK_KEY: Final[int] = 8221939


def _zero_irrelevant_limits(
    plan_type: PlanType, traffic_limit: int, device_limit: int
) -> tuple[int, int]:
    """A plan's type decides which limit applies; the other is zeroed
    (0 = unlimited on the panel). An applying limit can't be 0: unlimited is
    the type's to say. Idempotent, so it runs on every create and update."""
    applies_traffic = plan_type in (PlanType.TRAFFIC, PlanType.BOTH)
    applies_devices = plan_type in (PlanType.DEVICES, PlanType.BOTH)
    if (applies_traffic and traffic_limit < 1) or (applies_devices and device_limit < 1):
        raise ValidationError(
            f"Plan type '{plan_type}' needs its limits of at least 1",
            code=ErrorCode.PLAN_LIMIT_REQUIRED,
        )
    return (traffic_limit if applies_traffic else 0), (device_limit if applies_devices else 0)


def _check_trial_badge(is_trial: bool, badge: Optional[PlanBadge]) -> None:
    if is_trial and badge is not None:
        raise ValidationError("A trial plan can't carry a badge", code=ErrorCode.PLAN_TRIAL_BADGE)


def _check_trial_availability(availability: PlanAvailability) -> None:
    # the trial button never offers an EXISTING trial
    if availability == PlanAvailability.EXISTING:
        raise ValidationError(
            "A trial plan can't be limited to existing users",
            code=ErrorCode.PLAN_TRIAL_EXISTING_ACCESS,
        )


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

        overrides_by_duration: dict[int, list[PlanPriceOverrideDto]] = {}
        if duration_ids:
            override_result = await self.session.execute(
                select(PlanPriceOverride)
                .where(PlanPriceOverride.plan_duration_id.in_(duration_ids))
                .order_by(PlanPriceOverride.id)
            )
            for override_row in override_result.scalars():
                overrides_by_duration.setdefault(override_row.plan_duration_id, []).append(
                    PlanPriceOverrideDto(currency=override_row.currency, price=override_row.price)
                )

        durations_by_plan: dict[int, list[PlanDurationDto]] = {}
        for row in duration_rows:
            durations_by_plan.setdefault(row.plan_id, []).append(
                PlanDurationDto(
                    id=row.id,
                    days=row.days,
                    order_index=row.order_index,
                    base_price=row.base_price,
                    overrides=overrides_by_duration.get(row.id, []),
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
            badge=row.badge,
            icon_emoji_id=row.icon_emoji_id,
            icon_emoji_fallback=row.icon_emoji_fallback,
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
            allow_bonus_days=row.allow_bonus_days,
            allow_promocodes=row.allow_promocodes,
            discount_percent=row.discount_percent,
            discount_starts_at=row.discount_starts_at,
            discount_ends_at=row.discount_ends_at,
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
            raise NotFoundError(f"Plan '{plan_id}' not found", code=ErrorCode.PLAN_NOT_FOUND)
        return row

    async def get_by_id(self, plan_id: int) -> PlanDto:
        row = await self._get_or_raise(plan_id)
        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def create(self, data: CreatePlanDto) -> PlanDto:
        _check_trial_badge(data.is_trial, data.badge)
        await self.session.execute(select(func.pg_advisory_xact_lock(_PLAN_ORDER_LOCK_KEY)))
        count_result = await self.session.execute(select(func.count()).select_from(Plan))
        next_order_index = count_result.scalar_one()

        traffic_limit, device_limit = _zero_irrelevant_limits(
            data.type, data.traffic_limit, data.device_limit
        )
        assert data.public_code is not None  # filled in by CreatePlanUseCase
        row = Plan(
            public_code=data.public_code,
            name=data.name,
            description=data.description,
            tag=data.tag,
            badge=data.badge,
            icon_emoji_id=data.icon_emoji_id,
            icon_emoji_fallback=data.icon_emoji_fallback,
            type=data.type,
            availability=PlanAvailability.ALL,
            traffic_limit_strategy=data.traffic_limit_strategy,
            traffic_limit=traffic_limit,
            device_limit=device_limit,
            allowed_telegram_ids=[],
            allowed_emails=[],
            internal_squads=[],
            external_squad=None,
            order_index=next_order_index,
            is_active=False,
            is_trial=data.is_trial,
            allow_bonus_days=data.allow_bonus_days,
            allow_promocodes=data.allow_promocodes,
        )
        self.session.add(row)

        try:
            await self.session.flush()
        except IntegrityError as error:
            constraint = constraint_name(error)
            if constraint == "ix_plans_public_code":
                raise ConflictError(
                    f"Plan with public_code '{data.public_code}' already exists",
                    code=ErrorCode.PLAN_PUBLIC_CODE_TAKEN,
                ) from error
            if constraint == "ix_plans_name":
                raise ConflictError(
                    f"Plan with name '{data.name}' already exists", code=ErrorCode.PLAN_NAME_TAKEN
                ) from error
            raise

        await self.session.refresh(row)
        return self._to_dto(row, [])

    async def update(self, data: UpdatePlanDto) -> PlanDto:
        row = await self._get_or_raise(data.plan_id)
        was_trial = row.is_trial

        apply_partial_update(row, data, skip=frozenset({"plan_id", "cleared"}))
        if row.is_trial and not was_trial:
            _check_trial_availability(row.availability)
        for name in data.cleared:
            setattr(row, name, None)
        _check_trial_badge(row.is_trial, row.badge)

        if row.icon_emoji_id is None:
            row.icon_emoji_fallback = None

        row.traffic_limit, row.device_limit = _zero_irrelevant_limits(
            row.type, row.traffic_limit, row.device_limit
        )

        if row.is_active:
            if not row.internal_squads:
                raise ValidationError(
                    "Cannot activate a plan with no squads", code=ErrorCode.PLAN_NO_SQUADS
                )
            duration_count = await self.session.scalar(
                select(func.count()).select_from(PlanDuration).where(PlanDuration.plan_id == row.id)
            )
            if not duration_count:
                raise ValidationError(
                    "Cannot activate a plan with no durations", code=ErrorCode.PLAN_NO_DURATIONS
                )

        try:
            await self.session.flush()
        except IntegrityError as error:
            constraint = constraint_name(error)
            if constraint == "ix_plans_name":
                raise ConflictError(
                    f"Plan name '{data.name}' already exists", code=ErrorCode.PLAN_NAME_TAKEN
                ) from error
            raise

        await self.session.refresh(row)
        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def delete(self, plan_id: int) -> None:
        await self._get_or_raise(plan_id)
        try:
            await self.session.execute(delete(Plan).where(Plan.id == plan_id))
            await self.session.flush()
        except IntegrityError as error:
            constraint = constraint_name(error)
            if constraint == "promocodes_reward_plan_id_fkey":
                raise ConflictError(
                    f"Plan '{plan_id}' is still referenced by a promocode",
                    code=ErrorCode.PLAN_USED_BY_PROMOCODE,
                ) from error
            # not transactions: their plan_id is ON DELETE SET NULL, since an
            # order is provisioned from its own plan_snapshot
            raise ConflictError(
                f"Plan '{plan_id}' is still referenced elsewhere", code=ErrorCode.PLAN_IN_USE
            ) from error

    async def set_durations(self, data: SetPlanDurationsDto) -> PlanDto:
        row = await self._get_or_raise(data.plan_id)

        if row.is_active and not data.durations:
            raise ValidationError(
                "Cannot remove all durations from an active plan", code=ErrorCode.PLAN_NO_DURATIONS
            )

        seen_days: set[int] = set()
        for duration in data.durations:
            if duration.days in seen_days:
                raise ValidationError(
                    f"Duplicate duration of {duration.days} days",
                    code=ErrorCode.PLAN_DURATION_DUPLICATE,
                )
            seen_days.add(duration.days)

        await self.session.execute(select(func.pg_advisory_xact_lock(_PLAN_DURATIONS_LOCK_KEY)))
        # updated in place by days: a kept duration keeps its pinned per-currency prices
        existing = {
            row.days: row
            for row in await self.session.scalars(
                select(PlanDuration).where(PlanDuration.plan_id == data.plan_id)
            )
        }
        await self.session.execute(
            delete(PlanDuration).where(
                PlanDuration.plan_id == data.plan_id, PlanDuration.days.not_in(seen_days)
            )
        )
        for duration in data.durations:
            kept = existing.get(duration.days)
            if kept is None:
                self.session.add(
                    PlanDuration(
                        plan_id=data.plan_id,
                        days=duration.days,
                        order_index=duration.order_index,
                        base_price=duration.base_price,
                    )
                )
            else:
                kept.order_index = duration.order_index
                kept.base_price = duration.base_price
        await self.session.flush()

        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def set_price_override(self, data: SetPlanPriceOverrideDto) -> PlanDto:
        row = await self._get_or_raise(data.plan_id)

        duration_result = await self.session.execute(
            select(PlanDuration).where(
                PlanDuration.plan_id == data.plan_id, PlanDuration.days == data.days
            )
        )
        duration_row = duration_result.scalar_one_or_none()
        if duration_row is None:
            raise NotFoundError(
                f"Plan '{data.plan_id}' has no duration of '{data.days}' days",
                code=ErrorCode.PLAN_DURATION_NOT_FOUND,
            )

        if data.price is None:
            await self.session.execute(
                delete(PlanPriceOverride).where(
                    PlanPriceOverride.plan_duration_id == duration_row.id,
                    PlanPriceOverride.currency == data.currency,
                )
            )
        else:
            override_result = await self.session.execute(
                select(PlanPriceOverride).where(
                    PlanPriceOverride.plan_duration_id == duration_row.id,
                    PlanPriceOverride.currency == data.currency,
                )
            )
            override_row = override_result.scalar_one_or_none()
            if override_row is None:
                self.session.add(
                    PlanPriceOverride(
                        plan_duration_id=duration_row.id, currency=data.currency, price=data.price
                    )
                )
            else:
                override_row.price = data.price

        await self.session.flush()
        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def set_duration_base_price(self, data: SetPlanDurationBasePriceDto) -> PlanDto:
        row = await self._get_or_raise(data.plan_id)

        duration_result = await self.session.execute(
            select(PlanDuration).where(
                PlanDuration.plan_id == data.plan_id, PlanDuration.days == data.days
            )
        )
        duration_row = duration_result.scalar_one_or_none()
        if duration_row is None:
            raise NotFoundError(
                f"Plan '{data.plan_id}' has no duration of '{data.days}' days",
                code=ErrorCode.PLAN_DURATION_NOT_FOUND,
            )

        duration_row.base_price = data.base_price
        await self.session.flush()

        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def set_duration_base_prices(self, values: dict[int, Decimal]) -> None:
        for duration_id, base_price in values.items():
            row = await self.session.get(PlanDuration, duration_id)
            if row is None:
                raise NotFoundError(
                    f"Plan duration '{duration_id}' not found",
                    code=ErrorCode.PLAN_DURATION_NOT_FOUND,
                )
            row.base_price = base_price
        await self.session.flush()

    async def replace_duration_overrides(self, values: dict[int, dict[Currency, Decimal]]) -> None:
        for duration_id, prices in values.items():
            await self.session.execute(
                delete(PlanPriceOverride).where(PlanPriceOverride.plan_duration_id == duration_id)
            )
            self.session.add_all(
                PlanPriceOverride(plan_duration_id=duration_id, currency=currency, price=price)
                for currency, price in prices.items()
            )
        await self.session.flush()

    async def update_access(self, data: UpdatePlanAccessDto) -> PlanDto:
        if (
            data.availability == PlanAvailability.ALLOWED
            and not data.allowed_telegram_ids
            and not data.allowed_emails
        ):
            raise ValidationError(
                "availability=ALLOWED requires at least one allowed telegram id or email",
                code=ErrorCode.ALLOWED_LIST_EMPTY,
            )

        row = await self._get_or_raise(data.plan_id)
        if row.is_trial:
            _check_trial_availability(data.availability)
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

    async def update_discount(self, data: UpdatePlanDiscountDto) -> PlanDto:
        row = await self._get_or_raise(data.plan_id)
        row.discount_percent = data.discount_percent
        row.discount_starts_at = data.discount_starts_at
        row.discount_ends_at = data.discount_ends_at

        await self.session.flush()
        await self.session.refresh(row)
        durations_by_plan = await self._load_durations([row.id])
        return self._to_dto(row, durations_by_plan.get(row.id, []))

    async def reorder(self, data: ReorderPlansDto) -> list[PlanDto]:
        await self.session.execute(select(func.pg_advisory_xact_lock(_PLAN_ORDER_LOCK_KEY)))
        result = await self.session.execute(select(Plan))
        rows = {row.id: row for row in result.scalars()}

        if set(data.plan_ids) != set(rows) or len(data.plan_ids) != len(rows):
            raise ValidationError(
                "Reorder must include every existing plan id exactly once",
                code=ErrorCode.PLAN_REORDER_INCOMPLETE,
            )

        for index, plan_id in enumerate(data.plan_ids):
            rows[plan_id].order_index = index

        await self.session.flush()
        return await self.list_all()
