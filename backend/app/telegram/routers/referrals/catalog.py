from app.modules.dialogs import catalog, register_all_flow_metadata
from app.telegram.dialogs.state_pool import register_seed_state
from app.telegram.routers.referrals.handlers import on_redeem_days, on_withdraw_points
from app.telegram.states import Referrals


def register_referrals_catalog() -> None:
    register_all_flow_metadata()
    if catalog.has_action_handler("withdraw_points"):
        return

    catalog.bind_action_handler("withdraw_points", on_withdraw_points)
    catalog.bind_action_handler("redeem_days", on_redeem_days)

    register_seed_state("referrals.main", Referrals.MAIN)
