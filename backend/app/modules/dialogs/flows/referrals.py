from app.core.constants import DEFAULT_BANNER_NAME
from app.core.enums import ButtonLinkType, DialogFlow
from app.modules.dialogs import catalog


def register_referrals_metadata() -> None:
    if catalog.has_window("referrals.main"):
        return

    catalog.register_action_key("redeem_days")
    catalog.register_action_key("referral_qr")
    catalog.register_action_key("reset_referral_code")

    catalog.register_condition("has_points", lambda data: bool(data.get("has_points")))
    catalog.register_condition(
        "can_withdraw_points", lambda data: bool(data.get("can_withdraw_points"))
    )
    catalog.register_condition("has_bonus_days", lambda data: bool(data.get("has_bonus_days")))
    catalog.register_condition(
        "referral_reset_enabled", lambda data: bool(data.get("referral_reset_enabled"))
    )
    catalog.register_variable(
        "referral_url", lambda data: data.get("referral_url", ""), category="referral"
    )
    catalog.register_variable(
        "support_url", lambda data: data.get("support_url", ""), category="other"
    )

    catalog.register_window(
        catalog.CatalogWindow(
            key="referrals.main",
            flow=DialogFlow.REFERRALS,
            text_keys=("msg-referrals",),
            banner_name=DEFAULT_BANNER_NAME,
            text_variables=(
                "referrals_level_1",
                "referrals_level_2",
                "points",
                "bonus_days",
                "referral_url",
            ),
            buttons=(
                catalog.CatalogButton(
                    key="about",
                    text_key="btn-referrals.about",
                    row=0,
                    column=0,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="referrals.about",
                ),
                catalog.CatalogButton(
                    key="qr",
                    text_key="btn-referrals.qr",
                    row=1,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="referral_qr",
                ),
                catalog.CatalogButton(
                    key="share",
                    text_key="btn-referrals.share",
                    row=1,
                    column=1,
                    link_type=ButtonLinkType.URL,
                    url_value="https://t.me/share/url?url=${referral_url}",
                ),
                catalog.CatalogButton(
                    key="withdraw",
                    text_key="btn-referrals.withdraw",
                    row=2,
                    column=0,
                    link_type=ButtonLinkType.URL,
                    url_value="${support_url}",
                    visibility_condition="can_withdraw_points",
                ),
                catalog.CatalogButton(
                    key="redeem",
                    text_key="btn-referrals.redeem",
                    row=2,
                    column=1,
                    link_type=ButtonLinkType.ACTION,
                    action_key="redeem_days",
                    visibility_condition="has_bonus_days",
                ),
                catalog.CatalogButton(
                    key="reset_code",
                    text_key="btn-referrals.reset-code",
                    row=3,
                    column=0,
                    link_type=ButtonLinkType.ACTION,
                    action_key="reset_referral_code",
                    visibility_condition="referral_reset_enabled",
                ),
                catalog.CatalogButton(
                    key="back",
                    text_key="btn-back.general",
                    row=4,
                    column=0,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.main",
                ),
            ),
        )
    )

    catalog.register_window(
        catalog.CatalogWindow(
            key="referrals.about",
            flow=DialogFlow.REFERRALS,
            text_keys=("msg-referrals-about",),
            banner_name=DEFAULT_BANNER_NAME,
            text_variables=(
                "invitee_reward_amount",
                "invitee_reward_type",
                "reward_terms",
                "accrual_strategy",
                "reward_levels",
                "reward_type",
            ),
            buttons=(
                catalog.CatalogButton(
                    key="back",
                    text_key="btn-back.general",
                    row=0,
                    column=0,
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="referrals.main",
                ),
            ),
        )
    )
