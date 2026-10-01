from dishka import Provider, Scope, alias, provide

from app.core.ports import SubscriptionRevoker
from app.modules.subscriptions.addon_repository import AddOnRepository
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.subscriptions.usecases import (
    ActivateTrialSubscriptionUseCase,
    CreateAddOnUseCase,
    DeleteAddOnUseCase,
    DeleteAllDevicesUseCase,
    DeleteDeviceUseCase,
    DeleteSubscriptionUseCase,
    GetAddOnUseCase,
    GetAvailableTrialUseCase,
    GetSubscriptionUseCase,
    GrantAddOnUseCase,
    ListAddOnsUseCase,
    ListDevicesUseCase,
    ListSubscriptionsUseCase,
    PurchaseSubscriptionUseCase,
    ReissueSubscriptionUseCase,
    ReorderAddOnsUseCase,
    SetAddOnBasePriceUseCase,
    SetAddOnPriceOverrideUseCase,
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
    get_subscription_use_case = provide(GetSubscriptionUseCase)
    update_subscription_use_case = provide(UpdateSubscriptionUseCase)
    update_subscription_squads_use_case = provide(UpdateSubscriptionSquadsUseCase)
    delete_subscription_use_case = provide(DeleteSubscriptionUseCase)
    get_available_trial_use_case = provide(GetAvailableTrialUseCase)
    activate_trial_subscription_use_case = provide(ActivateTrialSubscriptionUseCase)
    list_addons_use_case = provide(ListAddOnsUseCase)
    get_add_on_use_case = provide(GetAddOnUseCase)
    list_devices_use_case = provide(ListDevicesUseCase)
    delete_device_use_case = provide(DeleteDeviceUseCase)
    delete_all_devices_use_case = provide(DeleteAllDevicesUseCase)
    create_addon_use_case = provide(CreateAddOnUseCase)
    update_addon_use_case = provide(UpdateAddOnUseCase)
    delete_addon_use_case = provide(DeleteAddOnUseCase)
    set_addon_base_price_use_case = provide(SetAddOnBasePriceUseCase)
    set_addon_price_override_use_case = provide(SetAddOnPriceOverrideUseCase)
    reorder_addons_use_case = provide(ReorderAddOnsUseCase)
    grant_addon_use_case = provide(GrantAddOnUseCase)
    purchase_subscription_use_case = provide(PurchaseSubscriptionUseCase)
    reissue_subscription_use_case = provide(ReissueSubscriptionUseCase)
    sync_subscription_status_use_case = provide(SyncSubscriptionStatusUseCase)
    panel_subscription_revoker = provide(PanelSubscriptionRevoker)
    subscription_revoker = alias(source=PanelSubscriptionRevoker, provides=SubscriptionRevoker)


def get_subscriptions_providers() -> list[Provider]:
    return [SubscriptionsProvider()]
