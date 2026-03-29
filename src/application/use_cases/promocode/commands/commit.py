from dataclasses import dataclass

from loguru import logger

from src.application.common import Interactor
from src.application.common.dao import PromocodeDao
from src.application.common.policy import Permission
from src.application.common.uow import UnitOfWork
from src.application.dto import PromocodeDto, UserDto
from src.application.use_cases.promocode.utils import (
    SUPPORTED_PROMOCODE_REWARD_TYPES,
    is_valid_promocode_reward,
)
from src.core.exceptions import PromocodeCodeAlreadyExistsError


@dataclass(frozen=True)
class CommitPromocodeResultDto:
    promocode: PromocodeDto
    is_created: bool = False
    is_updated: bool = False


class CommitPromocode(Interactor[PromocodeDto, CommitPromocodeResultDto]):
    required_permission = Permission.VIEW_PROMOCODE

    def __init__(self, uow: UnitOfWork, promocode_dao: PromocodeDao) -> None:
        self.uow = uow
        self.promocode_dao = promocode_dao

    async def _execute(self, actor: UserDto, promocode: PromocodeDto) -> CommitPromocodeResultDto:
        promocode.code = promocode.code.strip().upper()

        self._validate(promocode)

        async with self.uow:
            existing = await self.promocode_dao.get_by_code(promocode.code)

            if promocode.id is None:
                if existing:
                    raise PromocodeCodeAlreadyExistsError(promocode.code)

                created_promocode = await self.promocode_dao.create(promocode)
                await self.uow.commit()
                logger.info(f"{actor.log} Created promocode '{created_promocode.code}'")
                return CommitPromocodeResultDto(created_promocode, is_created=True)

            if existing and existing.id != promocode.id:
                raise PromocodeCodeAlreadyExistsError(promocode.code)

            updated_promocode = await self.promocode_dao.update(promocode.as_fully_changed())
            if not updated_promocode:
                raise ValueError(f"Promocode '{promocode.id}' not found")

            await self.uow.commit()
            logger.info(f"{actor.log} Updated promocode '{updated_promocode.code}'")
            return CommitPromocodeResultDto(updated_promocode, is_updated=True)

    def _validate(self, promocode: PromocodeDto) -> None:
        if len(promocode.code) < 3:
            raise ValueError("Promocode length must be at least 3 characters")

        if promocode.reward_type not in SUPPORTED_PROMOCODE_REWARD_TYPES:
            raise ValueError(f"Unsupported promocode type '{promocode.reward_type}'")

        if promocode.reward is None or not is_valid_promocode_reward(
            promocode.reward_type,
            promocode.reward,
        ):
            raise ValueError(f"Invalid promocode reward '{promocode.reward}'")

        if promocode.lifetime is not None and promocode.lifetime < 1:
            raise ValueError(f"Invalid promocode lifetime '{promocode.lifetime}'")

        if promocode.max_activations is not None and promocode.max_activations < 1:
            raise ValueError(f"Invalid promocode max activations '{promocode.max_activations}'")
