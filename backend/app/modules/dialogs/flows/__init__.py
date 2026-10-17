from app.modules.dialogs.flows.menu import register_menu_metadata
from app.modules.dialogs.flows.referrals import register_referrals_metadata
from app.modules.dialogs.flows.subscriptions import register_subscriptions_metadata


def register_all_flow_metadata() -> None:
    """Every flow's framework-agnostic catalog metadata; both the api and the
    telegram process call this."""
    register_menu_metadata()
    register_subscriptions_metadata()
    register_referrals_metadata()
