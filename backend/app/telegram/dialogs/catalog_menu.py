from app.modules.dialogs import catalog
from app.modules.dialogs.flows.menu import register_menu_metadata
from app.telegram.dialogs.state_pool import register_seed_state
from app.telegram.states import MainMenu


def register_menu_catalog() -> None:
    register_menu_metadata()  # idempotent; safe to re-enter

    # Idempotent guard -- routers/menu/__init__.py eagerly imports both `dialog`
    # and `handlers` submodules together (`from app.telegram.routers.menu import
    # dialog, handlers`). dialog.py calls this function at its own module level,
    # and (see the lazy import below) resolving `handlers` from a cold process
    # re-enters that same __init__.py import statement, which imports `dialog`
    # first -- and dialog.py's top level calls register_menu_catalog() again,
    # nested, before the outer call's own registration lines run. Both calls
    # are the same logical "register the menu flow" operation; the guard makes
    # the second (outer) call a no-op instead of hitting bind_action_handler's
    # already-bound guard. Reproducible by calling this function directly (e.g.
    # from a test) without dialog.py already imported.
    #
    # This checks has_action_handler rather than has_window: register_menu_metadata()
    # above always runs first and is independently idempotent, so by this point
    # windows are already registered on every call -- the thing that still needs
    # guarding is specifically "have handlers been bound yet."
    if catalog.has_action_handler("get_trial"):
        return

    # Lazy import -- see the guard comment above for why this needs to be
    # deferred to call time rather than a module-level import: it's what
    # triggers the re-entrant import chain in the first place. Same pattern
    # as translations/seed.py's fluent.syntax import.
    from app.telegram.routers.menu.handlers import (  # noqa: PLC0415
        on_device_delete_all_confirm,
        on_device_delete_confirm,
        on_get_trial,
        on_reissue_subscription_confirm,
    )

    # Re-check: the import above is exactly what can trigger the nested
    # re-entrant call described in the guard comment -- by the time control
    # returns here, that nested call may have already bound everything.
    if catalog.has_action_handler("get_trial"):
        return

    catalog.bind_action_handler("get_trial", on_get_trial)
    catalog.bind_action_handler("delete_device", on_device_delete_confirm)
    catalog.bind_action_handler("delete_all_devices", on_device_delete_all_confirm)
    catalog.bind_action_handler("reissue_subscription", on_reissue_subscription_confirm)

    register_seed_state("menu.main", MainMenu.MAIN)
    register_seed_state("menu.devices", MainMenu.DEVICES)
    register_seed_state("menu.device_confirm_delete", MainMenu.DEVICE_CONFIRM_DELETE)
    register_seed_state("menu.device_confirm_delete_all", MainMenu.DEVICE_CONFIRM_DELETE_ALL)
    register_seed_state("menu.device_confirm_reissue", MainMenu.DEVICE_CONFIRM_REISSUE)
