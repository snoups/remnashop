from app.modules.dialogs import catalog, register_all_flow_metadata
from app.telegram.dialogs.state_pool import register_seed_state
from app.telegram.routers.menu.handlers import (
    on_device_delete_all_confirm,
    on_device_delete_confirm,
    on_get_trial,
    on_reissue_subscription_confirm,
)
from app.telegram.states import MainMenu


def register_menu_catalog() -> None:
    register_all_flow_metadata()
    if catalog.has_action_handler("get_trial"):
        return

    catalog.bind_action_handler("get_trial", on_get_trial)
    catalog.bind_action_handler("delete_device", on_device_delete_confirm)
    catalog.bind_action_handler("delete_all_devices", on_device_delete_all_confirm)
    catalog.bind_action_handler("reissue_subscription", on_reissue_subscription_confirm)

    register_seed_state("menu.main", MainMenu.MAIN)
    register_seed_state("menu.devices", MainMenu.DEVICES)
    register_seed_state("menu.device_confirm_delete", MainMenu.DEVICE_CONFIRM_DELETE)
    register_seed_state("menu.device_confirm_delete_all", MainMenu.DEVICE_CONFIRM_DELETE_ALL)
    register_seed_state("menu.device_confirm_reissue", MainMenu.DEVICE_CONFIRM_REISSUE)
