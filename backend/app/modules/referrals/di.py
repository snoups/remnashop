from dishka import Provider, Scope, provide

from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.usecases import (
    AdjustUserPointsUseCase,
    AttachReferralUseCase,
    GetOwnReferralStatsUseCase,
    GetReferralSettingsUseCase,
    GetUserReferralStatsUseCase,
    ListReferralsUseCase,
    RequestPointsWithdrawalUseCase,
    UpdateReferralSettingsUseCase,
)


class ReferralsProvider(Provider):
    scope = Scope.REQUEST

    referral_repository = provide(ReferralRepository)
    attach_referral_use_case = provide(AttachReferralUseCase)
    request_points_withdrawal_use_case = provide(RequestPointsWithdrawalUseCase)
    adjust_user_points_use_case = provide(AdjustUserPointsUseCase)
    get_referral_settings_use_case = provide(GetReferralSettingsUseCase)
    update_referral_settings_use_case = provide(UpdateReferralSettingsUseCase)
    get_own_referral_stats_use_case = provide(GetOwnReferralStatsUseCase)
    get_user_referral_stats_use_case = provide(GetUserReferralStatsUseCase)
    list_referrals_use_case = provide(ListReferralsUseCase)


def get_referrals_providers() -> list[Provider]:
    return [ReferralsProvider()]
