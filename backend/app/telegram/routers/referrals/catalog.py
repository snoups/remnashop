from app.modules.dialogs import catalog, register_all_flow_metadata
from app.telegram.dialogs.state_pool import register_seed_state
from app.telegram.routers.referrals.handlers import (
    on_redeem_days,
    on_referral_qr,
    on_reset_referral_code,
)
from app.telegram.states import Referrals


def register_referrals_catalog() -> None:
    register_all_flow_metadata()
    if catalog.has_action_handler("redeem_days"):
        return

    catalog.bind_action_handler("redeem_days", on_redeem_days)
    catalog.bind_action_handler("referral_qr", on_referral_qr)
    catalog.bind_action_handler("reset_referral_code", on_reset_referral_code)

    register_seed_state("referrals.main", Referrals.MAIN)
