from dishka import Provider, Scope, provide

from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    ActivateTrialSubscriptionUseCase,
    CreateAddOnUseCase,
    DeleteAddOnUseCase,
    DeleteAllDevicesUseCase,
    DeleteDeviceUseCase,
    DeleteSubscriptionUseCase,
    GetAvailableTrialUseCase,
    GrantAddOnUseCase,
    ListAddOnsUseCase,
    ListDevicesUseCase,
    ListSubscriptionsUseCase,
    PurchaseSubscriptionUseCase,
    ReissueSubscriptionUseCase,
    ReorderAddOnsUseCase,
    SetAddOnPricesUseCase,
    SyncSubscriptionStatusUseCase,
    UpdateAddOnUseCase,
    UpdateSubscriptionSquadsUseCase,
    UpdateSubscriptionUseCase,
)


class SubscriptionsProvider(Provider):
    scope = Scope.REQUEST

    subscription_repository = provide(SubscriptionRepository)
    addon_repository = provide(AddOnRepository)
    lifecycle_service = provide(SubscriptionLifecycleService)
    list_subscriptions_use_case = provide(ListSubscriptionsUseCase)
    update_subscription_use_case = provide(UpdateSubscriptionUseCase)
    update_subscription_squads_use_case = provide(UpdateSubscriptionSquadsUseCase)
    delete_subscription_use_case = provide(DeleteSubscriptionUseCase)
    get_available_trial_use_case = provide(GetAvailableTrialUseCase)
    activate_trial_subscription_use_case = provide(ActivateTrialSubscriptionUseCase)
    list_addons_use_case = provide(ListAddOnsUseCase)
    list_devices_use_case = provide(ListDevicesUseCase)
    delete_device_use_case = provide(DeleteDeviceUseCase)
    delete_all_devices_use_case = provide(DeleteAllDevicesUseCase)
    create_addon_use_case = provide(CreateAddOnUseCase)
    update_addon_use_case = provide(UpdateAddOnUseCase)
    delete_addon_use_case = provide(DeleteAddOnUseCase)
    set_addon_prices_use_case = provide(SetAddOnPricesUseCase)
    reorder_addons_use_case = provide(ReorderAddOnsUseCase)
    grant_addon_use_case = provide(GrantAddOnUseCase)
    purchase_subscription_use_case = provide(PurchaseSubscriptionUseCase)
    reissue_subscription_use_case = provide(ReissueSubscriptionUseCase)
    sync_subscription_status_use_case = provide(SyncSubscriptionStatusUseCase)


def get_subscriptions_providers() -> list[Provider]:
    return [SubscriptionsProvider()]
