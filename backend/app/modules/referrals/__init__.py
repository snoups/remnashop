from app.modules.referrals.dto import (  # noqa: I001
    ReferralDto,
    ReferralRewardDto,
    ReferralSettingsDto,
    ReferralStatsDto,
    UpdateReferralSettingsDto,
)
from app.modules.referrals.repository import ReferralRepository

# di imported after dto/repository above: app.modules.subscriptions'
# usecases import ReferralRepository back from this package, and di's own
# chain (usecases -> events -> app.modules.subscriptions) re-enters this
# module before it finishes -- ReferralRepository must already be bound.
from app.modules.referrals.di import get_referrals_providers, get_referrals_revenue_providers
from app.modules.referrals.usecases import (
    AdjustUserPointsDto,
    AdjustUserPointsUseCase,
    AttachReferralDto,
    AttachReferralUseCase,
    GetOwnReferralStatsUseCase,
    GetReferralSettingsUseCase,
    GetUserReferralStatsUseCase,
    ListReferralsInput,
    ListReferralsUseCase,
    RequestPointsWithdrawalDto,
    RequestPointsWithdrawalUseCase,
    UpdateReferralSettingsUseCase,
)

__all__ = [
    "AdjustUserPointsDto",
    "AdjustUserPointsUseCase",
    "AttachReferralDto",
    "AttachReferralUseCase",
    "GetOwnReferralStatsUseCase",
    "GetReferralSettingsUseCase",
    "GetUserReferralStatsUseCase",
    "ListReferralsInput",
    "ListReferralsUseCase",
    "ReferralDto",
    "ReferralRepository",
    "ReferralRewardDto",
    "ReferralSettingsDto",
    "ReferralStatsDto",
    "RequestPointsWithdrawalDto",
    "RequestPointsWithdrawalUseCase",
    "UpdateReferralSettingsDto",
    "UpdateReferralSettingsUseCase",
    "get_referrals_providers",
    "get_referrals_revenue_providers",
]
