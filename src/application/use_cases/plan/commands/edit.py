from dataclasses import dataclass

from loguru import logger

from src.application.common import Cryptographer, Interactor
from src.application.common.dao import PlanDao
from src.application.common.policy import Permission
from src.application.dto import PlanDto, UserDto
from src.application.services import PricingService
from src.core.constants import TAG_REGEX
from src.core.enums import Currency, PlanType


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
            raise ValueError()

        if len(data.input_name) > 32:
            logger.warning(f"Plan name '{data.input_name}' exceeds 32 characters")
            raise ValueError()

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
