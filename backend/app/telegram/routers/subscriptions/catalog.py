from app.modules.dialogs import catalog, register_all_flow_metadata
from app.telegram.dialogs.state_pool import register_seed_state
from app.telegram.routers.subscriptions.handlers import (
    on_device_delete_all_confirm,
    on_device_delete_confirm,
    on_devices_back,
    on_open_devices,
    on_open_subscriptions,
    on_reissue_subscription_confirm,
    on_subscription_card_back,
)
from app.telegram.states import Subscriptions


def register_subscriptions_catalog() -> None:
    register_all_flow_metadata()
    if catalog.has_action_handler("open_subscriptions"):
        return

    catalog.bind_action_handler("open_subscriptions", on_open_subscriptions)
    catalog.bind_action_handler("open_devices", on_open_devices)
    catalog.bind_action_handler("devices_back", on_devices_back)
    catalog.bind_action_handler("subscription_card_back", on_subscription_card_back)
    catalog.bind_action_handler("delete_device", on_device_delete_confirm)
    catalog.bind_action_handler("delete_all_devices", on_device_delete_all_confirm)
    catalog.bind_action_handler("reissue_subscription", on_reissue_subscription_confirm)

    register_seed_state("subscriptions.list", Subscriptions.LIST)
    register_seed_state("subscriptions.card", Subscriptions.CARD)
    # window keys keep their menu.* names: they are stored rows admins may have edited
    register_seed_state("menu.devices", Subscriptions.DEVICES)
    register_seed_state("menu.device_confirm_delete", Subscriptions.DEVICE_CONFIRM_DELETE)
    register_seed_state("menu.device_confirm_delete_all", Subscriptions.DEVICE_CONFIRM_DELETE_ALL)
    register_seed_state("menu.device_confirm_reissue", Subscriptions.DEVICE_CONFIRM_REISSUE)
