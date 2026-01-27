import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Optional

from adaptix import Retort
from loguru import logger

from src.application.common import Cryptographer, Interactor
from src.application.common.dao import PlanDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import PlanDto, PlanDurationDto, PlanPriceDto, PlanSnapshotDto, UserDto
from src.application.services import PricingService
from src.core.constants import TAG_REGEX
from src.core.enums import Currency, PlanAvailability, PlanType
from src.core.exceptions import PlanNameAlreadyExistsError, SquadsEmptyError, TrialDurationError


class MovePlanUp(Interactor[int, None]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    def __init__(self, uow: UnitOfWork, plan_dao: PlanDao) -> None:
        self.uow = uow
        self.plan_dao = plan_dao

    async def _execute(self, actor: UserDto, plan_id: int) -> None:
        async with self.uow:
            plans = await self.plan_dao.get_all()
            plans.sort(key=lambda p: p.order_index)

            index = next((i for i, p in enumerate(plans) if p.id == plan_id), None)

            if index is None:
                logger.warning(f"Plan with ID '{plan_id}' not found for move operation")
                return

            if index == 0:
                plan = plans.pop(0)
                plans.append(plan)
                logger.debug(f"Plan '{plan_id}' moved from top to bottom")
            else:
                plans[index - 1], plans[index] = plans[index], plans[index - 1]
                logger.debug(f"Plan '{plan_id}' moved up one position")

            for i, p in enumerate(plans, start=1):
                p.order_index = i
                await self.plan_dao.update(p)

            await self.uow.commit()

        logger.info(f"{actor.log} Moved plan '{plan_id}' up successfully")


class DeletePlan(Interactor[int, None]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    def __init__(self, uow: UnitOfWork, plan_dao: PlanDao) -> None:
        self.uow = uow
        self.plan_dao = plan_dao

    async def _execute(self, actor: UserDto, plan_id: int) -> None:
        async with self.uow:
            await self.plan_dao.delete(plan_id)

            plans = await self.plan_dao.get_all()
            plans.sort(key=lambda p: p.order_index)

            for i, p in enumerate(plans, start=1):
                if p.order_index != i:
                    p.order_index = i
                    await self.plan_dao.update(p)

            await self.uow.commit()

        logger.info(f"{actor.log} Deleted plan ID '{plan_id}' and reordered remaining")


@dataclass(frozen=True)
class UpdatePlanNameDto:
    plan: PlanDto
    input_name: str


class UpdatePlanName(Interactor[UpdatePlanNameDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    def __init__(self, plan_dao: PlanDao, cryptographer: Cryptographer) -> None:
        self.plan_dao = plan_dao
        self.cryptographer = cryptographer

    async def _execute(self, actor: UserDto, data: UpdatePlanNameDto) -> PlanDto:
        existing_plan = await self.plan_dao.get_by_name(data.input_name)

        if existing_plan and existing_plan.id != data.plan.id:
            logger.warning(f"{actor.log} Tried to set duplicate plan name '{data.input_name}'")
            raise ValueError(f"Plan with name '{data.input_name}' already exists")

        data.plan.name = data.input_name
        data.plan.public_code = self.cryptographer.generate_short_code(data.plan.name, length=8)
        logger.info(f"{actor.log} Updated plan name in memory to '{data.input_name}'")
        return data.plan


@dataclass(frozen=True)
class UpdatePlanDescriptionDto:
    plan: PlanDto
    input_description: str


class UpdatePlanDescription(Interactor[UpdatePlanDescriptionDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    async def _execute(self, actor: UserDto, data: UpdatePlanDescriptionDto) -> PlanDto:
        if len(data.input_description) > 1024:
            logger.warning(
                f"{actor.log} Description too long: '{len(data.input_description)}' symbols"
            )
            raise ValueError("Description is too long")

        data.plan.description = data.input_description
        logger.info(f"{actor.log} Updated plan description in memory")
        return data.plan


@dataclass(frozen=True)
class UpdatePlanTagDto:
    plan: PlanDto
    input_tag: str


class UpdatePlanTag(Interactor[UpdatePlanTagDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    async def _execute(self, actor: UserDto, data: UpdatePlanTagDto) -> PlanDto:
        tag = data.input_tag.strip()

        if not TAG_REGEX.fullmatch(tag):
            logger.warning(f"{actor.log} Invalid plan tag format: '{tag}'")
            raise ValueError(f"Tag '{tag}' does not match required format")

        data.plan.tag = tag
        logger.info(f"{actor.log} Updated plan tag in memory to '{tag}'")
        return data.plan


@dataclass(frozen=True)
class UpdatePlanTypeDto:
    plan: PlanDto
    type: PlanType


class UpdatePlanType(Interactor[UpdatePlanTypeDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    async def _execute(self, actor: UserDto, data: UpdatePlanTypeDto) -> PlanDto:
        if data.type == PlanType.DEVICES and data.plan.device_limit == 0:
            data.plan.device_limit = 1
        elif data.type == PlanType.TRAFFIC and data.plan.traffic_limit == 0:
            data.plan.traffic_limit = 100
        elif data.type == PlanType.BOTH:
            if data.plan.traffic_limit == 0:
                data.plan.traffic_limit = 100
            if data.plan.device_limit == 0:
                data.plan.device_limit = 1

        data.plan.type = data.type

        logger.info(f"{actor.log} Updated plan type in memory to '{data.type}'")
        return data.plan


@dataclass(frozen=True)
class UpdatePlanTrafficDto:
    plan: PlanDto
    input_traffic_limit: str


class UpdatePlanTraffic(Interactor[UpdatePlanTrafficDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    async def _execute(self, actor: UserDto, data: UpdatePlanTrafficDto) -> PlanDto:
        if not (data.input_traffic_limit.isdigit() and int(data.input_traffic_limit) > 0):
            logger.warning(f"{actor.log} Invalid traffic limit value: '{data.input_traffic_limit}'")
            raise ValueError(
                f"Traffic limit must be a positive integer, got '{data.input_traffic_limit}'"
            )

        traffic_limit = int(data.input_traffic_limit)
        data.plan.traffic_limit = traffic_limit

        logger.info(f"{actor.log} Updated plan traffic limit in memory to '{traffic_limit}'")
        return data.plan


@dataclass(frozen=True)
class UpdatePlanDeviceDto:
    plan: PlanDto
    input_device_limit: str


class UpdatePlanDevice(Interactor[UpdatePlanDeviceDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    async def _execute(self, actor: UserDto, data: UpdatePlanDeviceDto) -> PlanDto:
        if not (data.input_device_limit.isdigit() and int(data.input_device_limit) > 0):
            logger.warning(f"{actor.log} Invalid device limit value: '{data.input_device_limit}'")
            raise ValueError(
                f"Device limit must be a positive integer, got '{data.input_device_limit}'"
            )

        device_limit = int(data.input_device_limit)
        data.plan.device_limit = device_limit

        logger.info(f"{actor.log} Updated plan device limit in memory to '{device_limit}'")
        return data.plan


@dataclass(frozen=True)
class RemovePlanDurationDto:
    plan: PlanDto
    duration: int


class RemovePlanDuration(Interactor[RemovePlanDurationDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    async def _execute(self, actor: UserDto, data: RemovePlanDurationDto) -> PlanDto:
        if len(data.plan.durations) <= 1:
            logger.warning(
                f"{actor.log} Failed to remove duration: plan must have at least one duration"
            )
            raise ValueError("Cannot remove the last duration of a plan")

        original_count = len(data.plan.durations)
        data.plan.durations = [d for d in data.plan.durations if d.days != data.duration]

        if len(data.plan.durations) == original_count:
            logger.warning(
                f"{actor.log} Duration '{data.duration}' not found in plan '{data.plan.id}'"
            )
            return data.plan

        logger.info(f"{actor.log} Removed duration '{data.duration}' from plan in memory")
        return data.plan


@dataclass(frozen=True)
class AddPlanDurationDto:
    plan: PlanDto
    input_duration: str


class AddPlanDuration(Interactor[AddPlanDurationDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    async def _execute(self, actor: UserDto, data: AddPlanDurationDto) -> PlanDto:
        if not (data.input_duration.isdigit() and int(data.input_duration) >= 0):
            logger.warning(f"{actor.log} Invalid duration input: '{data.input_duration}'")
            raise ValueError(f"Duration must be a positive integer, got '{data.input_duration}'")

        days = int(data.input_duration)

        if any(d.days == days for d in data.plan.durations):
            logger.warning(f"{actor.log} Duration '{days}' already exists in plan")
            raise ValueError(f"Duration '{days}' already exists")

        new_duration = PlanDurationDto(
            days=days,
            prices=[PlanPriceDto(currency=c, price=Decimal(100)) for c in Currency],
        )

        data.plan.durations.append(new_duration)
        logger.info(f"{actor.log} Added new duration '{days}' days to plan in memory")
        return data.plan


@dataclass(frozen=True)
class UpdatePlanPriceDto:
    plan: PlanDto
    duration: int
    currency: Currency
    input_price: str


class UpdatePlanPrice(Interactor[UpdatePlanPriceDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    def __init__(self, pricing_service: PricingService) -> None:
        self.pricing_service = pricing_service

    async def _execute(self, actor: UserDto, data: UpdatePlanPriceDto) -> PlanDto:
        try:
            new_price = self.pricing_service.parse_price(data.input_price, data.currency)
        except ValueError:
            logger.warning(f"{actor.log} Invalid price format: '{data.input_price}'")
            raise

        for duration in data.plan.durations:
            if duration.days == data.duration:
                for price_dto in duration.prices:
                    if price_dto.currency == data.currency:
                        price_dto.price = new_price
                        logger.info(
                            f"{actor.log} Updated price for duration '{data.duration}' "
                            f"days and currency '{data.currency}' to '{new_price}'"
                        )
                        return data.plan

        logger.warning(f"{actor.log} Price target not found for duration '{data.duration}'")
        raise ValueError("Target duration or currency not found in plan")


@dataclass(frozen=True)
class AddAllowedUserToPlanDto:
    plan: PlanDto
    input_telegram_id: str


class AddAllowedUserToPlan(Interactor[AddAllowedUserToPlanDto, PlanDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    async def _execute(self, actor: UserDto, data: AddAllowedUserToPlanDto) -> PlanDto:
        if not data.input_telegram_id.isdigit():
            logger.warning(f"{actor.log} Provided non-numeric user ID: '{data.input_telegram_id}'")
            raise ValueError(f"User ID must be numeric, got '{data.input_telegram_id}'")

        allowed_telegram_id = int(data.input_telegram_id)

        if allowed_telegram_id in data.plan.allowed_user_ids:
            logger.warning(f"{actor.log} User '{allowed_telegram_id}' is already in allowed list")
            raise ValueError(f"User '{allowed_telegram_id}' already allowed")

        data.plan.allowed_user_ids.append(allowed_telegram_id)

        logger.info(
            f"{actor.log} Added user '{allowed_telegram_id}' to allowed list of plan in memory"
        )
        return data.plan


@dataclass(frozen=True)
class CommitPlanResultDto:
    plan: Optional[PlanDto] = None
    is_created: bool = False
    is_updated: bool = False


class CommitPlan(Interactor[PlanDto, CommitPlanResultDto]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    def __init__(self, uow: UnitOfWork, plan_dao: PlanDao, cryptographer: Cryptographer) -> None:
        self.uow = uow
        self.plan_dao = plan_dao
        self.cryptographer = cryptographer

    async def _execute(self, actor: UserDto, plan: PlanDto) -> CommitPlanResultDto:
        if not plan.internal_squads:
            logger.warning(f"{actor.log} Commit failed: squads list is empty")
            raise SquadsEmptyError()

        if plan.is_trial and len(plan.durations) > 1:
            logger.warning(
                f"{actor.log} Commit failed: trial plan has '{len(plan.durations)}' durations"
            )
            raise TrialDurationError()

        if plan.type == PlanType.DEVICES:
            plan.traffic_limit = 0
        elif plan.type == PlanType.TRAFFIC:
            plan.device_limit = 0
        elif plan.type == PlanType.UNLIMITED:
            plan.traffic_limit = 0
            plan.device_limit = 0

        if plan.availability != PlanAvailability.ALLOWED:
            plan.allowed_user_ids = []

        async with self.uow:
            if plan.id:
                await self.plan_dao.update(plan.as_fully_changed())
                logger.info(f"{actor.log} Updated existing plan '{plan.name}' with ID '{plan.id}'")
                await self.uow.commit()
                return CommitPlanResultDto(plan, is_updated=True)

            existing = await self.plan_dao.get_by_name(plan.name)
            if existing:
                logger.warning(f"{actor.log} Plan name '{plan.name}' already exists")
                raise PlanNameAlreadyExistsError()

            plan.public_code = self.cryptographer.generate_short_code(plan.name, length=8)
            new_plan = await self.plan_dao.create(plan)
            await self.uow.commit()

        logger.info(f"{actor.log} Created new plan '{new_plan.name}'")
        return CommitPlanResultDto(new_plan, is_created=True)


class ParsePlansImport(Interactor[str, list[PlanDto]]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    def __init__(self, retort: Retort) -> None:
        self.retort = retort

    async def _execute(self, actor: UserDto, raw_plans: str) -> list[PlanDto]:
        logger.debug(f"{actor.log} Parsing plans import file")

        json_plans = json.loads(raw_plans)
        if isinstance(json_plans, dict):
            raw_data = [json_plans]

        plans = [self.retort.load(item, PlanDto) for item in raw_data]

        if not plans:
            logger.warning(f"{actor.log} Import aborted: file contains no plans")
            raise ValueError("Import file is empty")

        for plan in plans:
            plan.id = None
            plan.created_at = None
            plan.updated_at = None

            for duration in plan.durations:
                duration.id = None

                for price in duration.prices:
                    price.id = None

        logger.info(f"{actor.log} Successfully parsed '{len(plans)}' plans from import")
        return plans


class ExportPlans(Interactor[list[int], str]):
    required_permission = Permission.REMNASHOP_PLAN_EDITOR

    def __init__(self, plan_dao: PlanDao, retort: Retort) -> None:
        self.plan_dao = plan_dao
        self.retort = retort

    async def _execute(self, actor: UserDto, plan_ids: list[int]) -> str:
        logger.debug(f"{actor.log} Exporting '{len(plan_ids)}' plans to JSON")

        exported_data = []
        for plan_id in plan_ids:
            plan = await self.plan_dao.get_by_id(plan_id)

            if plan:
                plan.id = None
                plan.created_at = None
                plan.updated_at = None

                for duration in plan.durations:
                    duration.id = None

                    for price in duration.prices:
                        price.id = None

                exported_data.append(self.retort.dump(plan))

        if not exported_data:
            logger.warning(f"{actor.log} No plans found for export with IDs '{plan_ids}'")
            raise ValueError("No plans available for export")

        return json.dumps(exported_data, indent=4, ensure_ascii=False)


@dataclass(frozen=True)
class MatchPlanDto:
    snapshot: PlanSnapshotDto
    plans: list[PlanDto]


class MatchPlan(Interactor[MatchPlanDto, Optional[PlanDto]]):
    required_permission = None

    async def _execute(self, actor: UserDto, data: MatchPlanDto) -> Optional[PlanDto]:
        snapshot = data.snapshot

        for plan in data.plans:
            if self._is_plan_equal(snapshot, plan):
                return plan

        logger.warning(f"{actor.log} No matching plan found for snapshot '{snapshot.id}'")
        return None

    def _is_plan_equal(self, snapshot: PlanSnapshotDto, plan: PlanDto) -> bool:
        return (
            snapshot.id == plan.id
            and snapshot.tag == plan.tag
            and snapshot.type == plan.type
            and snapshot.traffic_limit == plan.traffic_limit
            and snapshot.device_limit == plan.device_limit
            and snapshot.traffic_limit_strategy == plan.traffic_limit_strategy
            and sorted(snapshot.internal_squads) == sorted(plan.internal_squads)
            and snapshot.external_squad == plan.external_squad
        )


@dataclass(frozen=True)
class ToggleUserPlanAccessDto:
    plan_id: int
    telegram_id: int


class ToggleUserPlanAccess(Interactor[ToggleUserPlanAccessDto, None]):
    required_permission = Permission.USER_EDITOR

    def __init__(self, uow: UnitOfWork, plan_dao: PlanDao):
        self.uow = uow
        self.plan_dao = plan_dao

    async def _execute(self, actor: UserDto, data: ToggleUserPlanAccessDto) -> None:
        async with self.uow:
            plan = await self.plan_dao.get_by_id(data.plan_id)
            if not plan:
                raise ValueError(f"Plan '{data.plan_id}' not found")

            allowed_ids = list(plan.allowed_user_ids)
            if data.telegram_id not in allowed_ids:
                allowed_ids.append(data.telegram_id)
                action = "Granted"
            else:
                allowed_ids.remove(data.telegram_id)
                action = "Revoked"

            plan.allowed_user_ids = allowed_ids
            await self.plan_dao.update(plan)
            await self.uow.commit()

        logger.info(
            f"{actor.log} {action} access to plan '{data.plan_id}' for user '{data.telegram_id}'"
        )


PLAN_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    AddAllowedUserToPlan,
    AddPlanDuration,
    CommitPlan,
    DeletePlan,
    MovePlanUp,
    RemovePlanDuration,
    UpdatePlanDescription,
    UpdatePlanDevice,
    UpdatePlanName,
    UpdatePlanPrice,
    UpdatePlanTag,
    UpdatePlanTraffic,
    UpdatePlanType,
    ParsePlansImport,
    ExportPlans,
    MatchPlan,
    ToggleUserPlanAccess,
)
