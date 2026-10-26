from app.core.constants import DEFAULT_BANNER_NAME
from app.core.enums import ButtonLinkType, DialogFlow
from app.modules.dialogs import catalog


def register_menu_metadata() -> None:
    # idempotent: app.telegram.routers.menu.catalog.register_menu_catalog()
    # calls it on every entry
    if catalog.has_window("menu.main"):
        return

    catalog.register_action_key("get_trial")
    catalog.register_action_key("delete_device")
    catalog.register_action_key("delete_all_devices")
    catalog.register_action_key("reissue_subscription")
    for key in ("purchase_new", "open_subscriptions", "promocode", "legal_documents"):
        catalog.register_action_key(key)

    catalog.register_condition("trial_available", lambda data: bool(data.get("trial_available")))
    catalog.register_condition(
        "trial_paid_available", lambda data: bool(data.get("trial_paid_available"))
    )
    catalog.register_condition("has_device_limit", lambda data: bool(data.get("has_device_limit")))
    # one visibility_condition per button, so both checks fold into this one
    catalog.register_condition(
        "connectable", lambda data: bool(data.get("connectable")) and bool(data.get("connect_url"))
    )
    catalog.register_condition("has_devices", lambda data: bool(data.get("has_devices")))
    catalog.register_condition(
        "has_subscriptions", lambda data: data.get("subscriptions_count", 0) > 0
    )
    catalog.register_condition("can_purchase", lambda data: bool(data.get("can_purchase")))
    catalog.register_condition("referral_enabled", lambda data: bool(data.get("referral_enabled")))
    catalog.register_condition("legal_available", lambda data: bool(data.get("legal_available")))
    catalog.register_condition("cabinet_available", lambda data: bool(data.get("cabinet_url")))

    # the first active subscription's; a user with several gets that one
    catalog.register_variable(
        "subscription_url", lambda data: data.get("connect_url", ""), category="subscription"
    )
    catalog.register_variable(
        "cabinet_url", lambda data: data.get("cabinet_url", ""), category="other"
    )
    catalog.register_variable("user_name", lambda data: data.get("name", ""), category="user")
    catalog.register_variable("user_points", lambda data: data.get("points", ""), category="user")
    catalog.register_variable("user_id", lambda data: data.get("telegram_id", ""), category="user")
    catalog.register_variable(
        "user_bonus_days", lambda data: data.get("bonus_days", 0), category="user"
    )
    catalog.register_variable(
        "user_discount", lambda data: data.get("discount", ""), category="user"
    )
    catalog.register_variable(
        "subscriptions_count", lambda data: data.get("subscriptions_count", 0), category="user"
    )
    catalog.register_variable(
        "trial_price", lambda data: data.get("trial_price", ""), category="user"
    )

    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.main",
            flow=DialogFlow.MENU,
            text_keys=("msg-main-menu",),
            banner_name=DEFAULT_BANNER_NAME,
            # rendered with the bot's translator, so only menu_getter has them
            text_variables=(
                "subscription_status",
                "subscription_traffic_limit",
                "subscription_device_limit",
                "subscription_expire_at",
                "subscription_block",
            ),
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
                    key="trial_paid",
                    text_key="btn-menu.trial-paid",
                    row=1,
                    column=1,
                    link_type=ButtonLinkType.ACTION,
                    action_key="get_trial",
                    visibility_condition="trial_paid_available",
                ),
                catalog.CatalogButton(
                    key="subscriptions",
                    text_key="btn-menu.subscriptions",
                    row=2,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="open_subscriptions",
                    visibility_condition="has_subscriptions",
                ),
                catalog.CatalogButton(
                    key="purchase",
                    text_key="btn-menu.purchase",
                    row=3,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="purchase_new",
                    visibility_condition="can_purchase",
                ),
                catalog.CatalogButton(
                    key="promocode",
                    text_key="btn-menu.promocode",
                    row=4,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="promocode",
                ),
                catalog.CatalogButton(
                    key="referrals",
                    text_key="btn-menu.referrals",
                    row=4,
                    column=1,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="referrals.main",
                    visibility_condition="referral_enabled",
                ),
                catalog.CatalogButton(
                    key="legal",
                    text_key="btn-menu.legal",
                    row=5,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="legal_documents",
                    visibility_condition="legal_available",
                ),
                catalog.CatalogButton(
                    key="cabinet",
                    text_key="btn-menu.web-cabinet",
                    row=6,
                    column=0,
                    link_type=ButtonLinkType.WEB_APP,
                    url_value="${cabinet_url}",
                    visibility_condition="cabinet_available",
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
                    target_window_key="subscriptions.card",
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
