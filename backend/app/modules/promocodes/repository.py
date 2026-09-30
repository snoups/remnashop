from typing import Optional

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.errors import constraint_name
from app.core.db.models.promocode import Promocode, PromocodeActivation
from app.core.db.partial_update import apply_partial_update
from app.core.enums import PromocodeRewardType
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.promocodes.dto import (
    CreatePromocodeDto,
    PromocodeActivationDto,
    PromocodeDto,
    PromocodeRewardTotalsDto,
    UpdatePromocodeDto,
    UserPromocodeActivationDto,
)


class PromocodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: Promocode) -> PromocodeDto:
        return PromocodeDto(
            id=row.id,
            code=row.code,
            is_active=row.is_active,
            reward_type=row.reward_type,
            reward=row.reward,
            reward_addon_id=row.reward_addon_id,
            reward_plan_id=row.reward_plan_id,
            reward_duration_days=row.reward_duration_days,
            availability=row.availability,
            allowed_user_ids=list(row.allowed_user_ids or []),
            expires_at=row.expires_at,
            max_activations=row.max_activations,
            is_reusable=row.is_reusable,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _activation_to_dto(self, row: PromocodeActivation) -> PromocodeActivationDto:
        return PromocodeActivationDto(
            id=row.id,
            promocode_id=row.promocode_id,
            user_id=row.user_id,
            subscription_id=row.subscription_id,
            activated_at=row.activated_at,
        )

    async def _get_or_raise(self, promocode_id: int) -> Promocode:
        row = await self.session.get(Promocode, promocode_id)
        if row is None:
            raise NotFoundError(f"Promocode '{promocode_id}' not found")
        return row

    async def get_by_id(self, promocode_id: int) -> PromocodeDto:
        return self._to_dto(await self._get_or_raise(promocode_id))

    async def get_by_code(self, code: str) -> Optional[PromocodeDto]:
        row = await self.session.scalar(select(Promocode).where(Promocode.code == code))
        return self._to_dto(row) if row is not None else None

    async def list_all(self) -> list[PromocodeDto]:
        result = await self.session.execute(select(Promocode).order_by(Promocode.id))
        return [self._to_dto(row) for row in result.scalars()]

    async def create(self, data: CreatePromocodeDto) -> PromocodeDto:
        row = Promocode(
            code=data.code,
            is_active=True,
            reward_type=data.reward_type,
            reward=data.reward,
            reward_addon_id=data.reward_addon_id,
            reward_plan_id=data.reward_plan_id,
            reward_duration_days=data.reward_duration_days,
            availability=data.availability,
            allowed_user_ids=data.allowed_user_ids,
            expires_at=data.expires_at,
            max_activations=data.max_activations,
            is_reusable=data.is_reusable,
        )
        self.session.add(row)

        try:
            await self.session.flush()
        except IntegrityError as error:
            constraint = constraint_name(error)
            if constraint == "ix_promocodes_code":
                raise ConflictError(f"Promocode with code '{data.code}' already exists") from error
            raise ConflictError(
                "Promocode could not be created due to a conflicting value"
            ) from error

        await self.session.refresh(row)
        return self._to_dto(row)

    async def update(self, data: UpdatePromocodeDto) -> PromocodeDto:
        row = await self._get_or_raise(data.promocode_id)

        apply_partial_update(row, data, skip=frozenset({"promocode_id"}))

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def delete(self, promocode_id: int) -> None:
        row = await self._get_or_raise(promocode_id)
        await self.session.delete(row)
        await self.session.flush()

    async def claim_activation(
        self, promocode_id: int, user_id: int, subscription_id: Optional[int]
    ) -> PromocodeActivationDto:
        # Locks the promocode row for the rest of this transaction so a
        # concurrent claim on the same promocode serializes behind this one --
        # max_activations/already-activated below are read from this locked
        # row, not from a value the caller read before locking, so the check
        # is atomic against concurrent claims. main's own migration history
        # (0036) dropped a unique constraint here and left this exact race
        # "guarded in application logic" with no lock -- this closes it.
        locked = await self.session.execute(
            select(Promocode).where(Promocode.id == promocode_id).with_for_update()
        )
        try:
            promocode_row = locked.scalar_one()
        except NoResultFound as error:
            raise NotFoundError(f"Promocode '{promocode_id}' not found") from error

        if promocode_row.max_activations is not None:
            count_result = await self.session.execute(
                select(func.count())
                .select_from(PromocodeActivation)
                .where(PromocodeActivation.promocode_id == promocode_id)
            )
            if count_result.scalar_one() >= promocode_row.max_activations:
                raise ValidationError(f"Promocode '{promocode_row.code}' activation limit reached")

        if not promocode_row.is_reusable:
            # exists(), not scalar_one_or_none(): a code toggled from reusable
            # to single-use leaves users with several activations, and asking
            # for exactly one there raises instead of refusing the claim.
            already_activated = await self.session.scalar(
                select(
                    exists().where(
                        PromocodeActivation.promocode_id == promocode_id,
                        PromocodeActivation.user_id == user_id,
                    )
                )
            )
            if already_activated:
                raise ValidationError(
                    f"Promocode '{promocode_row.code}' already activated by this user"
                )

        row = PromocodeActivation(
            promocode_id=promocode_id, user_id=user_id, subscription_id=subscription_id
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return self._activation_to_dto(row)

    async def get_activations_count(self, promocode_id: int) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(PromocodeActivation)
            .where(PromocodeActivation.promocode_id == promocode_id)
        )
        return result.scalar_one()

    async def count_activations_by_promocode(self) -> dict[int, int]:
        stmt = select(PromocodeActivation.promocode_id, func.count()).group_by(
            PromocodeActivation.promocode_id
        )
        return dict((await self.session.execute(stmt)).tuples().all())

    async def count_activations(self) -> tuple[int, int]:
        # (activations, distinct users)
        stmt = select(func.count(), func.count(func.distinct(PromocodeActivation.user_id)))
        activations, users = (await self.session.execute(stmt)).tuples().one()
        return activations, users

    async def reward_totals_by_type(self) -> dict[PromocodeRewardType, PromocodeRewardTotalsDto]:
        stmt = (
            select(
                Promocode.reward_type,
                func.count(),
                func.sum(Promocode.reward),
                func.sum(Promocode.reward_duration_days),
            )
            .select_from(PromocodeActivation)
            .join(Promocode, Promocode.id == PromocodeActivation.promocode_id)
            .group_by(Promocode.reward_type)
        )
        return {
            reward_type: PromocodeRewardTotalsDto(
                count=count, reward_sum=reward_sum or 0, duration_days_sum=duration_days_sum or 0
            )
            for reward_type, count, reward_sum, duration_days_sum in (
                await self.session.execute(stmt)
            ).tuples()
        }

    async def list_activations_paginated(
        self, promocode_id: int, *, page: int = 1, page_size: int = 50
    ) -> tuple[list[PromocodeActivationDto], int]:
        condition = PromocodeActivation.promocode_id == promocode_id
        total = await self.session.scalar(
            select(func.count()).select_from(PromocodeActivation).where(condition)
        )
        rows = await self.session.scalars(
            select(PromocodeActivation)
            .where(condition)
            .order_by(PromocodeActivation.activated_at.desc(), PromocodeActivation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [self._activation_to_dto(row) for row in rows], total or 0

    async def get_activation_by_user(
        self, promocode_id: int, user_id: int
    ) -> Optional[PromocodeActivationDto]:
        result = await self.session.execute(
            select(PromocodeActivation)
            .where(
                PromocodeActivation.promocode_id == promocode_id,
                PromocodeActivation.user_id == user_id,
            )
            .order_by(PromocodeActivation.activated_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return self._activation_to_dto(row) if row is not None else None

    async def list_activations_by_user(self, user_id: int) -> list[UserPromocodeActivationDto]:
        rows = await self.session.execute(
            select(PromocodeActivation, Promocode)
            .join(Promocode, Promocode.id == PromocodeActivation.promocode_id)
            .where(PromocodeActivation.user_id == user_id)
            .order_by(PromocodeActivation.activated_at.desc())
        )
        return [
            UserPromocodeActivationDto(
                activation_id=activation.id,
                promocode_id=promo.id,
                code=promo.code,
                reward_type=promo.reward_type,
                reward=promo.reward,
                reward_duration_days=promo.reward_duration_days,
                activated_at=activation.activated_at,
            )
            for activation, promo in rows.tuples()
        ]
