from app.modules.dialogs import catalog, register_all_flow_metadata
from app.telegram.dialogs.state_pool import register_seed_state
from app.telegram.routers.legal.handlers import on_legal_documents
from app.telegram.routers.menu.handlers import on_get_trial, on_show_connect_problem
from app.telegram.routers.promocode.handlers import on_promocode
from app.telegram.states import MainMenu


def register_menu_catalog() -> None:
    register_all_flow_metadata()
    if catalog.has_action_handler("get_trial"):
        return

    catalog.bind_action_handler("get_trial", on_get_trial)
    catalog.bind_action_handler("promocode", on_promocode)
    catalog.bind_action_handler("legal_documents", on_legal_documents)
    catalog.bind_action_handler("show_connect_problem", on_show_connect_problem)

    register_seed_state("menu.main", MainMenu.MAIN)
