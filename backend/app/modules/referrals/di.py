from typing import cast

from dishka import Provider, Scope, alias, provide, provide_all

from app.core.ports import ReferrerLookup
from app.modules.referrals.dispatch import BonusRenewalDispatch
from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.tasks import resume_bonus_renewal_task
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
    ResumeBonusRenewalUseCase,
    ReverseReferralRewardsUseCase,
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
        ReverseReferralRewardsUseCase,
        GetUserReferralRevenueUseCase,
        RedeemBonusDaysUseCase,
        ResumeBonusRenewalUseCase,
    )
    referrer_lookup = alias(source=ReferralRepository, provides=ReferrerLookup)

    @provide(scope=Scope.APP)
    def bonus_renewal_dispatch(self) -> BonusRenewalDispatch:
        return cast(BonusRenewalDispatch, resume_bonus_renewal_task)


def get_referrals_providers() -> list[Provider]:
    return [ReferralsProvider()]
