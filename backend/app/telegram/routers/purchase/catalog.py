from app.modules.dialogs import catalog, register_all_flow_metadata
from app.telegram.routers.purchase.handlers import (
    on_purchase_change,
    on_purchase_new,
    on_purchase_renew,
)


def register_purchase_catalog() -> None:
    register_all_flow_metadata()
    if catalog.has_action_handler("purchase_new"):
        return

    catalog.bind_action_handler("purchase_new", on_purchase_new)
    catalog.bind_action_handler("purchase_renew", on_purchase_renew)
    catalog.bind_action_handler("purchase_change", on_purchase_change)
