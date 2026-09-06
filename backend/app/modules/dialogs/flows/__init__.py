from app.modules.dialogs.flows.menu import register_menu_metadata


def register_all_flow_metadata() -> None:
    """Register every flow's framework-agnostic catalog metadata.

    The one seam both the api and telegram processes call. Adding a new flow
    later means adding one line here, not touching either process's lifespan.
    """
    register_menu_metadata()
