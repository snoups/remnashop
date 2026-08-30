import importlib
import inspect
import pkgutil

import app.modules
from app.core.security.permissions import Permission
from app.core.usecase import UseCase

_BUNDLED_EXCEPTIONS = frozenset(
    {Permission.ADMINS_MANAGE, Permission.API_TOKENS_MANAGE, Permission.OWN_ACCOUNT_MANAGE}
)


def _discover_use_case_classes() -> list[type[UseCase]]:
    classes: list[type[UseCase]] = []
    for module_info in pkgutil.iter_modules(app.modules.__path__):
        try:
            usecases_pkg = importlib.import_module(f"app.modules.{module_info.name}.usecases")
        except ModuleNotFoundError:
            continue
        for sub_info in pkgutil.walk_packages(
            usecases_pkg.__path__, prefix=f"{usecases_pkg.__name__}."
        ):
            submodule = importlib.import_module(sub_info.name)
            for _, obj in inspect.getmembers(submodule, inspect.isclass):
                if (
                    issubclass(obj, UseCase)
                    and obj is not UseCase
                    and obj.__module__ == submodule.__name__
                ):
                    classes.append(obj)
    return classes


def test_required_permission_is_unique_per_use_case() -> None:
    # A shared required_permission across two usecases means an OWNER can't
    # grant one without the other, and an API token can't be scoped to less
    # than the bundle -- docs/architecture/permissions-roles.md calls this a
    # real capability leak, not a style nit. Two named exceptions stay
    # deliberately bundled (see that doc's granularity rule); everything
    # else must be 1:1, checked here instead of by hand.
    by_permission: dict[Permission, list[str]] = {}
    for cls in _discover_use_case_classes():
        permission = cls.required_permission
        if (
            permission is None
            or permission is Permission.PUBLIC
            or permission in _BUNDLED_EXCEPTIONS
        ):
            continue
        by_permission.setdefault(permission, []).append(cls.__qualname__)

    duplicates = {
        permission: names for permission, names in by_permission.items() if len(names) > 1
    }
    assert duplicates == {}, f"required_permission shared across usecases: {duplicates}"


def test_discovery_actually_found_use_cases() -> None:
    # Guards the guard: if discovery silently found zero usecases (e.g. a
    # package layout change), the assertion above would trivially pass on an
    # empty dict.
    assert len(_discover_use_case_classes()) > 20


def test_public_permission_is_exempt_from_uniqueness() -> None:
    class _FakeUseCaseA(UseCase[None, None]):
        required_permission = Permission.PUBLIC

        async def _execute(self, actor, data):  # type: ignore[no-untyped-def]
            return None

    class _FakeUseCaseB(UseCase[None, None]):
        required_permission = Permission.PUBLIC

        async def _execute(self, actor, data):  # type: ignore[no-untyped-def]
            return None

    # Simulates what _discover_use_case_classes() would find if two real
    # usecases both used PUBLIC -- the uniqueness check itself must not
    # flag this pair, unlike a real shared capability permission.
    by_permission: dict[Permission, list[str]] = {}
    for cls in (_FakeUseCaseA, _FakeUseCaseB):
        permission = cls.required_permission
        if (
            permission is None
            or permission is Permission.PUBLIC
            or permission in _BUNDLED_EXCEPTIONS
        ):
            continue
        by_permission.setdefault(permission, []).append(cls.__qualname__)

    assert by_permission == {}
