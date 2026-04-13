from src.application.common import Interactor
from src.application.common.dao import ReferralDao, UserDao
from src.application.common.policy import Permission
from src.application.dto import ReferralStatisticsDto, UserDto


class GetReferralStatistics(Interactor[None, ReferralStatisticsDto]):
    required_permission = Permission.VIEW_STATISTICS

    def __init__(self, referral_dao: ReferralDao, user_dao: UserDao) -> None:
        self.referral_dao = referral_dao
        self.user_dao = user_dao

    async def _execute(self, actor: UserDto, data: None) -> ReferralStatisticsDto:
        stats = await self.referral_dao.get_stats()

        if stats.top_referrer_telegram_id:
            referrer = await self.user_dao.get_by_telegram_id(stats.top_referrer_telegram_id)

            if referrer:
                stats.top_referrer_username = referrer.username

        return stats
