from dishka import Provider, Scope, alias, provide, provide_all

from app.core.ports import ReferrerLookup
from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.usecases import (
    AdjustUserBonusDaysUseCase,
    AdjustUserPointsUseCase,
    AssignReferralRewardsUseCase,
    AttachReferralOnRegistrationUseCase,
    GetOwnReferralStatsUseCase,
    GetReferralSettingsUseCase,
    GetReferralSummaryUseCase,
    GetUserReferralLinksUseCase,
    GetUserReferralRevenueUseCase,
    GetUserReferralStatsUseCase,
    ListInvitedUsersUseCase,
    ListReferralsUseCase,
    RedeemBonusDaysUseCase,
    RequestPointsWithdrawalUseCase,
    ResetReferralCodeUseCase,
    ResetReferralSettingsUseCase,
    UpdateReferralSettingsUseCase,
)


class ReferralsProvider(Provider):
    scope = Scope.REQUEST

    referral_repository = provide(ReferralRepository)
    use_cases = provide_all(
        RequestPointsWithdrawalUseCase,
        AdjustUserPointsUseCase,
        AdjustUserBonusDaysUseCase,
        GetReferralSettingsUseCase,
        UpdateReferralSettingsUseCase,
        GetOwnReferralStatsUseCase,
        GetUserReferralStatsUseCase,
        ListReferralsUseCase,
        ListInvitedUsersUseCase,
        GetReferralSummaryUseCase,
        GetUserReferralLinksUseCase,
        ResetReferralCodeUseCase,
        ResetReferralSettingsUseCase,
        AttachReferralOnRegistrationUseCase,
        AssignReferralRewardsUseCase,
        GetUserReferralRevenueUseCase,
        RedeemBonusDaysUseCase,
    )
    referrer_lookup = alias(source=ReferralRepository, provides=ReferrerLookup)


def get_referrals_providers() -> list[Provider]:
    return [ReferralsProvider()]
