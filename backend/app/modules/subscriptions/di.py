from typing import cast

from dishka import Provider, Scope, alias, provide, provide_all

from app.core.ports import SubscriptionRevoker
from app.modules.subscriptions.dispatch import GrantAddOnDispatch, PurchaseSubscriptionDispatch
from app.modules.subscriptions.eligibility import PurchaseEligibility
from app.modules.subscriptions.idempotency_repository import PurchaseIdempotencyRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.subscriptions.rollback import PurchaseRollbackService
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.subscriptions.tasks import grant_addon_task, purchase_subscription_task
from app.modules.subscriptions.usecases import (
    ActivateTrialSubscriptionUseCase,
    AdminDeleteAllDevicesUseCase,
    AdminDeleteDeviceUseCase,
    AdminListDevicesUseCase,
    AdminReissueSubscriptionUseCase,
    ChangeSubscriptionPlanUseCase,
    DeleteAllDevicesUseCase,
    DeleteDeviceUseCase,
    DeleteSubscriptionUseCase,
    FulfillPurchaseUseCase,
    GetAvailableTrialUseCase,
    GetSubscriptionUseCase,
    GrantAddOnUseCase,
    GrantSubscriptionUseCase,
    HandleRemnawaveWebhookUseCase,
    ListActivePlansUseCase,
    ListDevicesUseCase,
    ListOwnActiveSubscriptionsUseCase,
    ListSubscriptionsUseCase,
    PruneIdempotencyKeysUseCase,
    PublishPanelEventUseCase,
    PurchaseSubscriptionUseCase,
    ReconcileSubscriptionsUseCase,
    ReissueSubscriptionUseCase,
    ResetSubscriptionTrafficUseCase,
    SetSubscriptionEnabledUseCase,
    SyncSubscriptionStatusUseCase,
    UpdateSubscriptionSquadsUseCase,
    UpdateSubscriptionUseCase,
)


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
        GetAvailableTrialUseCase,
        ActivateTrialSubscriptionUseCase,
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
        FulfillPurchaseUseCase,
        ReconcileSubscriptionsUseCase,
        PruneIdempotencyKeysUseCase,
    )
    subscription_revoker = alias(source=PanelSubscriptionRevoker, provides=SubscriptionRevoker)

    @provide(scope=Scope.APP)
    def purchase_subscription_dispatch(self) -> PurchaseSubscriptionDispatch:
        return cast(PurchaseSubscriptionDispatch, purchase_subscription_task)

    @provide(scope=Scope.APP)
    def grant_addon_dispatch(self) -> GrantAddOnDispatch:
        return cast(GrantAddOnDispatch, grant_addon_task)


def get_subscriptions_providers() -> list[Provider]:
    return [SubscriptionsProvider()]
