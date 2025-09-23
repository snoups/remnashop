from typing import Optional

from aiogram import Bot
from fluentogram import TranslatorHub
from redis.asyncio import Redis

from src.core.config import AppConfig
from src.core.enums import PromocodeRewardType
from src.infrastructure.database import UnitOfWork
from src.infrastructure.database.models.dto import PromocodeDto
from src.infrastructure.redis import RedisRepository

from .base import BaseService


class PromocodeService(BaseService):
    uow: UnitOfWork

    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        redis_client: Redis,
        redis_repository: RedisRepository,
        translator_hub: TranslatorHub,
        #
        uow: UnitOfWork,
    ) -> None:
        super().__init__(config, bot, redis_client, redis_repository, translator_hub)
        self.uow = uow

    async def create(self, promocode: PromocodeDto) -> PromocodeDto:  # type: ignore
        pass

    async def get(self, promocode_id: int) -> Optional[PromocodeDto]:
        db_promocode = await self.uow.repository.promocodes.get(promocode_id)
        return PromocodeDto.from_model(db_promocode)

    async def get_by_code(self, promocode_code: str) -> Optional[PromocodeDto]:
        db_promocode = await self.uow.repository.promocodes.get_by_code(promocode_code)
        return PromocodeDto.from_model(db_promocode)

    async def get_all(self) -> list[PromocodeDto]:
        db_promocode = await self.uow.repository.promocodes.get_all()
        return PromocodeDto.from_model_list(db_promocode)

    async def update(self, promocode: PromocodeDto) -> Optional[PromocodeDto]:
        db_updated_promocode = await self.uow.repository.promocodes.update(
            promocode_id=promocode.id,  # type: ignore[arg-type]
            **promocode.changed_data,
        )
        return PromocodeDto.from_model(db_updated_promocode)

    async def delete(self, promocode_id: int) -> bool:
        return await self.uow.repository.promocodes.delete(promocode_id)

    async def filter_by_type(self, promocode_type: PromocodeRewardType) -> list[PromocodeDto]:
        db_promocodes = await self.uow.repository.promocodes.filter_by_type(promocode_type)
        return PromocodeDto.from_model_list(db_promocodes)

    async def filter_active(self, is_active: bool = True) -> list[PromocodeDto]:
        db_promocodes = await self.uow.repository.promocodes.filter_active(is_active)
        return PromocodeDto.from_model_list(db_promocodes)
