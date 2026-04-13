from dataclasses import dataclass
from typing import Optional

from src.application.common import Interactor
from src.application.common.dao import TransactionDao
from src.application.common.policy import Permission
from src.application.dto import GatewayStatsDto, UserDto


@dataclass(frozen=True)
class TransactionStatisticsDto:
    total_transactions: int
    completed_transactions: int
    free_transactions: int
    popular_gateway: Optional[str]
    gateway_stats: list[GatewayStatsDto]


class GetTransactionStatistics(Interactor[None, TransactionStatisticsDto]):
    required_permission = Permission.VIEW_STATISTICS

    def __init__(self, transaction_dao: TransactionDao) -> None:
        self.transaction_dao = transaction_dao

    async def _execute(self, actor: UserDto, data: None) -> TransactionStatisticsDto:
        total = await self.transaction_dao.count_total()
        completed = await self.transaction_dao.count_completed()
        free = await self.transaction_dao.count_free()
        gateway_stats = await self.transaction_dao.get_gateway_stats()

        popular_gateway = None
        if len(gateway_stats) > 1:
            popular_gateway = max(gateway_stats, key=lambda s: s.paid_count).gateway_type

        return TransactionStatisticsDto(
            total_transactions=total,
            completed_transactions=completed,
            free_transactions=free,
            popular_gateway=popular_gateway,
            gateway_stats=gateway_stats,
        )
