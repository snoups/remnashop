from dishka import Provider, Scope, provide

from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.usecases import (
    AdjustUserPointsUseCase,
    AttachReferralUseCase,
    GetOwnReferralStatsUseCase,
    GetReferralSettingsUseCase,
    GetReferralSummaryUseCase,
    GetUserReferralLinksUseCase,
    GetUserReferralStatsUseCase,
    ListInvitedUsersUseCase,
    ListReferralsUseCase,
    RequestPointsWithdrawalUseCase,
    ResetReferralCodeUseCase,
    ResetReferralSettingsUseCase,
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
    list_invited_users_use_case = provide(ListInvitedUsersUseCase)
    get_referral_summary_use_case = provide(GetReferralSummaryUseCase)
    get_user_referral_links_use_case = provide(GetUserReferralLinksUseCase)
    reset_referral_code_use_case = provide(ResetReferralCodeUseCase)
    reset_referral_settings_use_case = provide(ResetReferralSettingsUseCase)


def get_referrals_providers() -> list[Provider]:
    return [ReferralsProvider()]


def get_referrals_revenue_providers() -> list[Provider]:
    # separate: needs payments and pricing, which only the api container wires.
    # Imported here, not at module level: payments -> subscriptions -> plans -> referrals
    # would re-enter payments before it finishes loading.
    from app.modules.referrals.usecases.get_user_referral_revenue import (  # noqa: PLC0415
        GetUserReferralRevenueUseCase,
    )

    provider = Provider(scope=Scope.REQUEST)
    provider.provide(GetUserReferralRevenueUseCase)
    return [provider]
