from app.core.constants import DEFAULT_BANNER_NAME
from app.core.enums import ButtonLinkType, DialogFlow
from app.modules.dialogs import catalog


def register_menu_metadata() -> None:
    # Idempotent -- app.telegram.routers.menu.catalog.register_menu_catalog() calls
    # this on every entry, so it must be safe to call more than once.
    if catalog.has_window("menu.main"):
        return

    catalog.register_action_key("get_trial")
    catalog.register_action_key("delete_device")
    catalog.register_action_key("delete_all_devices")
    catalog.register_action_key("reissue_subscription")

    catalog.register_condition("trial_available", lambda data: bool(data.get("trial_available")))
    catalog.register_condition("has_device_limit", lambda data: bool(data.get("has_device_limit")))
    # The original Url widget's `when=F["connectable"] & F["connect_url"]` ANDs two
    # conditions; this schema allows one visibility_condition per button, so both checks
    # fold into this single condition to keep behavior identical.
    catalog.register_condition(
        "connectable", lambda data: bool(data.get("connectable")) and bool(data.get("connect_url"))
    )
    catalog.register_condition("has_devices", lambda data: bool(data.get("has_devices")))

    # the first active subscription's -- a user with several gets that one
    catalog.register_variable(
        "subscription_url", lambda data: data.get("connect_url", ""), category="subscription"
    )
    catalog.register_variable("user_name", lambda data: data.get("name", ""), category="user")
    catalog.register_variable("user_points", lambda data: data.get("points", ""), category="user")

    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.main",
            flow=DialogFlow.MENU,
            text_keys=("msg-main-menu",),
            banner_name=DEFAULT_BANNER_NAME,
            buttons=(
                catalog.CatalogButton(
                    key="connect",
                    text_key="btn-menu.connect",
                    row=0,
                    column=0,
                    link_type=ButtonLinkType.URL,
                    url_value="${subscription_url}",
                    visibility_condition="connectable",
                ),
                catalog.CatalogButton(
                    key="trial",
                    text_key="btn-menu.trial",
                    row=1,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="get_trial",
                    visibility_condition="trial_available",
                ),
                catalog.CatalogButton(
                    key="devices",
                    text_key="btn-menu.devices",
                    row=2,
                    column=0,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.devices",
                    visibility_condition="has_device_limit",
                ),
            ),
        )
    )

    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.devices",
            flow=DialogFlow.MENU,
            text_keys=("msg-menu-devices",),
            banner_name=DEFAULT_BANNER_NAME,
            text_variables=("devices_current", "devices_max"),
            buttons=(
                catalog.CatalogButton(
                    key="delete_all",
                    text_key="btn-devices.delete-all",
                    row=0,
                    column=0,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.device_confirm_delete_all",
                    visibility_condition="has_devices",
                ),
                catalog.CatalogButton(
                    key="reissue",
                    text_key="btn-devices.reissue",
                    row=1,
                    column=0,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.device_confirm_reissue",
                ),
                catalog.CatalogButton(
                    key="back",
                    text_key="btn-back.general",
                    row=2,
                    column=0,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.main",
                ),
            ),
        )
    )

    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.device_confirm_delete",
            flow=DialogFlow.MENU,
            text_keys=("msg-menu-devices-confirm-delete",),
            banner_name=DEFAULT_BANNER_NAME,
            buttons=(
                catalog.CatalogButton(
                    key="confirm_delete",
                    text_key="btn-devices.confirm-delete",
                    row=0,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="delete_device",
                ),
                catalog.CatalogButton(
                    key="back",
                    text_key="btn-back.general",
                    row=0,
                    column=1,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.devices",
                ),
            ),
        )
    )

    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.device_confirm_delete_all",
            flow=DialogFlow.MENU,
            text_keys=("msg-menu-devices-confirm-delete-all",),
            banner_name=DEFAULT_BANNER_NAME,
            buttons=(
                catalog.CatalogButton(
                    key="confirm_delete_all",
                    text_key="btn-devices.confirm-delete",
                    row=0,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="delete_all_devices",
                ),
                catalog.CatalogButton(
                    key="back",
                    text_key="btn-back.general",
                    row=0,
                    column=1,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.devices",
                ),
            ),
        )
    )

    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.device_confirm_reissue",
            flow=DialogFlow.MENU,
            text_keys=("msg-menu-devices-confirm-reissue",),
            banner_name=DEFAULT_BANNER_NAME,
            buttons=(
                catalog.CatalogButton(
                    key="confirm_reissue",
                    text_key="btn-devices.confirm-reissue",
                    row=0,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="reissue_subscription",
                ),
                catalog.CatalogButton(
                    key="cancel",
                    text_key="btn-devices.cancel-reissue",
                    row=0,
                    column=1,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.devices",
                ),
            ),
        )
    )
