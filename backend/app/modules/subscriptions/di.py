from typing import cast

from dishka import Provider, Scope, alias, provide, provide_all

from app.modules.subscriptions.dispatch import (
    GrantAddOnDispatch,
    PanelSyncDispatch,
    PurchaseSubscriptionDispatch,
)
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.subscriptions.rollback import PurchaseRollbackService
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.subscriptions.tasks import (
    grant_addon_task,
    purchase_subscription_task,
    run_panel_sync_task,
)
from app.modules.subscriptions.usage import PanelTrafficUsage
from app.modules.subscriptions.usecases import (
    ActivateTrialSubscriptionUseCase,
    AdminDeleteAllDevicesUseCase,
    AdminDeleteDeviceUseCase,
    AdminListDevicesUseCase,
    AdminReissueSubscriptionUseCase,
    ApplyChannelMembershipUseCase,
    ChangeSubscriptionPlanUseCase,
    DeleteAllDevicesUseCase,
    DeleteDeviceUseCase,
    DeleteSubscriptionUseCase,
    DeleteUserSubscriptionsUseCase,
    FulfillPurchaseUseCase,
    GetAvailableTrialUseCase,
    GetPanelSyncStatusUseCase,
    GetSubscriptionPanelDiffUseCase,
    GetSubscriptionUseCase,
    GrantAddOnUseCase,
    GrantSubscriptionUseCase,
    HandleRemnawaveWebhookUseCase,
    ListActivePlansUseCase,
    ListDevicesUseCase,
    ListOwnActiveSubscriptionsUseCase,
    ListOwnSubscriptionsUsageUseCase,
    ListOwnSubscriptionsUseCase,
    ListPanelSquadsUseCase,
    ListSubscriptionsUseCase,
    PruneIdempotencyKeysUseCase,
    PublishPanelEventUseCase,
    PullSubscriptionFromPanelUseCase,
    PurchaseSubscriptionUseCase,
    PushSubscriptionToPanelUseCase,
    ReissueSubscriptionUseCase,
    ResetSubscriptionTrafficUseCase,
    SetSubscriptionEnabledUseCase,
    StartPanelSyncFromUseCase,
    StartPanelSyncToUseCase,
    SyncAllFromPanelUseCase,
    SyncAllToPanelUseCase,
    SyncSubscriptionStatusUseCase,
    UpdateSubscriptionSquadsUseCase,
    UpdateSubscriptionUseCase,
)
from app.modules.users import SubscriptionRevoker


class SubscriptionsProvider(Provider):
    scope = Scope.REQUEST

    services = provide_all(
        SubscriptionRepository,
        SubscriptionStatsRepository,
        PurchaseIdempotencyRepository,
        SubscriptionLifecycleService,
        PurchaseEligibility,
        PanelSubscriptionRevoker,
        PurchaseRollbackService,
        PanelTrafficUsage,
    )
    use_cases = provide_all(
        ListSubscriptionsUseCase,
        GetSubscriptionUseCase,
        UpdateSubscriptionUseCase,
        AdminDeleteAllDevicesUseCase,
        AdminDeleteDeviceUseCase,
        AdminListDevicesUseCase,
        AdminReissueSubscriptionUseCase,
        ResetSubscriptionTrafficUseCase,
        SetSubscriptionEnabledUseCase,
        ChangeSubscriptionPlanUseCase,
        GrantSubscriptionUseCase,
        UpdateSubscriptionSquadsUseCase,
        DeleteSubscriptionUseCase,
        DeleteUserSubscriptionsUseCase,
        GetAvailableTrialUseCase,
        ActivateTrialSubscriptionUseCase,
        ApplyChannelMembershipUseCase,
        ListDevicesUseCase,
        DeleteDeviceUseCase,
        DeleteAllDevicesUseCase,
        GrantAddOnUseCase,
        PurchaseSubscriptionUseCase,
        ReissueSubscriptionUseCase,
        SyncSubscriptionStatusUseCase,
        ListActivePlansUseCase,
        HandleRemnawaveWebhookUseCase,
        PublishPanelEventUseCase,
        ListOwnActiveSubscriptionsUseCase,
        ListOwnSubscriptionsUseCase,
        ListOwnSubscriptionsUsageUseCase,
        FulfillPurchaseUseCase,
        GetPanelSyncStatusUseCase,
        GetSubscriptionPanelDiffUseCase,
        ListPanelSquadsUseCase,
        PullSubscriptionFromPanelUseCase,
        PushSubscriptionToPanelUseCase,
        StartPanelSyncFromUseCase,
        StartPanelSyncToUseCase,
        SyncAllFromPanelUseCase,
        SyncAllToPanelUseCase,
        PruneIdempotencyKeysUseCase,
    )
    subscription_revoker = alias(source=PanelSubscriptionRevoker, provides=SubscriptionRevoker)

    @provide(scope=Scope.APP)
    def purchase_subscription_dispatch(self) -> PurchaseSubscriptionDispatch:
        return cast(PurchaseSubscriptionDispatch, purchase_subscription_task)

    @provide(scope=Scope.APP)
    def grant_addon_dispatch(self) -> GrantAddOnDispatch:
        return cast(GrantAddOnDispatch, grant_addon_task)

    @provide(scope=Scope.APP)
    def panel_sync_dispatch(self) -> PanelSyncDispatch:
        return cast(PanelSyncDispatch, run_panel_sync_task)


def get_subscriptions_providers() -> list[Provider]:
    return [SubscriptionsProvider()]
