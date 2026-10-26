from app.core.constants import DEFAULT_BANNER_NAME
from app.core.enums import ButtonLinkType, DialogFlow
from app.modules.dialogs import catalog


def register_subscriptions_metadata() -> None:
    if catalog.has_window("subscriptions.list"):
        return

    catalog.register_action_key("purchase_renew")
    catalog.register_action_key("purchase_change")
    catalog.register_action_key("subscription_card_back")

    # a trial is neither renewed nor changed: a purchase replaces it, link and all
    catalog.register_condition(
        "paid_subscription",
        lambda data: data.get("subscription") is not None and not data["subscription"].is_trial,
    )
    catalog.register_condition(
        "trial_subscription",
        lambda data: data.get("subscription") is not None and data["subscription"].is_trial,
    )

    catalog.register_window(
        catalog.CatalogWindow(
            key="subscriptions.list",
            flow=DialogFlow.SUBSCRIPTION,
            text_keys=("msg-subscriptions-list",),
            banner_name=DEFAULT_BANNER_NAME,
            buttons=(
                catalog.CatalogButton(
                    key="purchase",
                    text_key="btn-subscriptions.purchase",
                    row=0,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="purchase_new",
                    visibility_condition="can_purchase",
                ),
                catalog.CatalogButton(
                    key="back",
                    text_key="btn-back.general",
                    row=1,
                    column=0,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.main",
                ),
            ),
        )
    )

    catalog.register_window(
        catalog.CatalogWindow(
            key="subscriptions.card",
            flow=DialogFlow.SUBSCRIPTION,
            text_keys=("msg-subscription-card",),
            banner_name=DEFAULT_BANNER_NAME,
            text_variables=(
                "plan_name",
                "status",
                "expire_at",
                "traffic_limit",
                "device_limit",
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
                    key="devices",
                    text_key="btn-menu.devices",
                    row=1,
                    column=0,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.devices",
                    visibility_condition="has_device_limit",
                ),
                catalog.CatalogButton(
                    key="renew",
                    text_key="btn-subscription.renew",
                    row=2,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="purchase_renew",
                    visibility_condition="paid_subscription",
                ),
                catalog.CatalogButton(
                    key="change",
                    text_key="btn-subscription.change",
                    row=2,
                    column=1,
                    link_type=ButtonLinkType.ACTION,
                    action_key="purchase_change",
                    visibility_condition="paid_subscription",
                ),
                catalog.CatalogButton(
                    key="purchase",
                    text_key="btn-subscriptions.purchase",
                    row=2,
                    column=2,
                    link_type=ButtonLinkType.ACTION,
                    action_key="purchase_new",
                    visibility_condition="trial_subscription",
                ),
                catalog.CatalogButton(
                    key="back",
                    text_key="btn-back.general",
                    row=3,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="subscription_card_back",
                ),
            ),
        )
    )
