import importlib
import inspect
import pkgutil
from typing import Any

from fastapi.routing import APIRoute, APIRouter

import app.modules
from app.api.dependencies.admin import require_admin


def _discover_admin_routers() -> list[tuple[str, Any]]:
    routers = []
    for module_info in pkgutil.iter_modules(app.modules.__path__):
        try:
            admin_module = importlib.import_module(
                f"app.modules.{module_info.name}.api.admin_router"
            )
        except ModuleNotFoundError:
            continue
        for attr_name, attr_value in inspect.getmembers(
            admin_module, lambda obj: isinstance(obj, APIRouter)
        ):
            routers.append((f"{module_info.name}.{attr_name}", attr_value))
    return routers


def _requires_admin(route: APIRoute) -> bool:
    # walks sub-dependencies too: require_admin_user reaches require_admin
    pending = list(route.dependant.dependencies)
    while pending:
        dep = pending.pop()
        if dep.call is require_admin:
            return True
        pending.extend(dep.dependencies)
    return False


def test_every_admin_router_route_requires_admin() -> None:
    # admin_router.py's entire reason to exist is "privileged only" (see
    # docs/architecture/api-routers.md) -- a route landing here without
    # require_admin is reachable by any authenticated actor, which is an
    # auth-bypass, not just a style slip. Discovers admin_router.py modules
    # dynamically so a future module can't silently skip this check.
    missing = [
        f"{module_name}: {sorted(route.methods or [])} {route.path}"
        for module_name, router in _discover_admin_routers()
        for route in router.routes
        if isinstance(route, APIRoute) and not _requires_admin(route)
    ]
    assert missing == [], f"admin_router.py routes missing require_admin: {missing}"


def test_discovery_actually_found_the_known_admin_routers() -> None:
    # Guards the guard: if discovery silently found zero routers (e.g. a package
    # layout change breaks the app.modules.*.api.admin_router convention), the
    # test above would trivially pass on an empty list -- assert real coverage.
    discovered = {label for label, _ in _discover_admin_routers()}
    assert discovered == {
        "advertising.router",
        "announcements.router",
        "analytics.router",
        "api_tokens.router",
        "auth.sessions_router",
        "auth.user_sessions_router",
        "backups.router",
        "banners.router",
        "emoji_packs.router",
        "blacklist.router",
        "dialogs.router",
        "event_log.router",
        "gateways.router",
        "oauth.router",
        "overview.router",
        "passkeys.router",
        "plans.addons_router",
        "plans.pricing_router",
        "plans.router",
        "promocodes.router",
        "referrals.router",
        "settings.router",
        "subscriptions.router",
        "transactions.router",
        "translations.locales_router",
        "translations.router",
        "users.router",
        "users.admins_router",
    }
