from typing import Final

from src.application.common import Interactor

from .queries.plans import GetPlanStatistics
from .queries.promocodes import GetPromocodeStatistics
from .queries.referrals import GetReferralStatistics
from .queries.subscriptions import GetSubscriptionStatistics
from .queries.transactions import GetTransactionStatistics
from .queries.users import GetUsersStatistics, GetUserStatistics

STATISTICS_USE_CASES: Final[tuple[type[Interactor], ...]] = (
    GetUsersStatistics,
    GetSubscriptionStatistics,
    GetTransactionStatistics,
    GetPlanStatistics,
    GetPromocodeStatistics,
    GetReferralStatistics,
    GetUserStatistics,
)
