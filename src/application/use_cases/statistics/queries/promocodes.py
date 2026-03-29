from src.application.common import Interactor
from src.application.common.dao import PromocodeDao
from src.application.dto import PromocodeStatisticsDto, UserDto


class GetPromocodeStatistics(Interactor[None, PromocodeStatisticsDto]):
    required_permission = None

    def __init__(self, promocode_dao: PromocodeDao) -> None:
        self.promocode_dao = promocode_dao

    async def _execute(self, actor: UserDto, data: None) -> PromocodeStatisticsDto:
        return await self.promocode_dao.get_statistics()
