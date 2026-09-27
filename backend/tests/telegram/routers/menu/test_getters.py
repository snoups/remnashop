from unittest.mock import AsyncMock, MagicMock

import pytest
from fluentogram.exceptions import KeyNotFoundError

from app.core.constants import USER_KEY
from app.core.enums import Locale
from app.modules.dialogs import catalog
from app.modules.dialogs.flows.menu import register_menu_metadata
from app.modules.subscriptions import GetAvailableTrialUseCase
from app.telegram.routers.menu.getters import device_confirm_delete_getter, menu_getter


def _echo_translator() -> MagicMock:
    """Echoes the key back, the way the real runner would return a value -- but
    raises on the icon keys nothing seeded, which is what fluentogram does and
    what label_with_icon relies on to tell "no icon" from "an icon"."""

    def get(key: str, **kwargs: object) -> str:
        if key.endswith("-icon") or key.endswith("-icon-id"):
            raise KeyNotFoundError(key)
        return key

    return MagicMock(get=get)


@pytest.fixture(autouse=True)
def _menu_catalog():
    # menu_getter now resolves catalog variables (resolve_variable_kwargs), and other
    # test modules wipe the global catalog via catalog._reset_for_tests(), so pin a
    # known-registered state here rather than relying on import-time registration.
    catalog._reset_for_tests()
    register_menu_metadata()
    yield
    catalog._reset_for_tests()


async def test_menu_getter_includes_rendered_buttons(
    config, banner_repository, subscription_repository, monkeypatch
) -> None:
    dialog_manager = MagicMock()
    dialog_manager.middleware_data = {USER_KEY: MagicMock(id=1, language=Locale.EN, name="Test")}

    fake_cache = MagicMock()
    fake_cache.get_window = AsyncMock(return_value=MagicMock(banner_name="menu"))

    async def _fake_render(*args, **kwargs):
        return [[{"id": 1, "text": "x"}]]

    monkeypatch.setattr("app.telegram.routers.menu.getters.render_dialog_buttons", _fake_render)

    get_available_trial = AsyncMock(spec=GetAvailableTrialUseCase)
    get_available_trial.return_value = MagicMock(is_trial_available=False, plan=None)

    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value = _echo_translator()

    data = await menu_getter.__dishka_orig_func__(
        dialog_manager=dialog_manager,
        config=config,
        banner_repository=banner_repository,
        subscription_repository=subscription_repository,
        get_available_trial=get_available_trial,
        i18n=i18n,
        dialog_config_cache=fake_cache,
    )

    assert data["buttons"] == [[{"id": 1, "text": "x"}]]
    assert "connect_text" not in data
    assert "trial_text" not in data
    assert "devices_text" not in data
    assert data["subscription_text"] == "btn-menu.subscription"


async def test_menu_getter_passes_name_variable_to_menu_text(
    config, banner_repository, subscription_repository, monkeypatch
) -> None:
    # `name` is a permanently registered catalog variable (menu.register_menu_metadata),
    # so this test relies on that registration rather than adding a scoped one.
    assert "name" in catalog.variable_keys()

    # `name` is a reserved MagicMock kwarg, so it must be assigned after construction.
    user = MagicMock(id=1, language=Locale.EN)
    user.name = "Test"
    dialog_manager = MagicMock()
    dialog_manager.middleware_data = {USER_KEY: user}

    fake_cache = MagicMock()
    fake_cache.get_window = AsyncMock(return_value=MagicMock(banner_name="menu"))

    async def _fake_render(*args, **kwargs):
        return [[{"id": 1, "text": "x"}]]

    monkeypatch.setattr("app.telegram.routers.menu.getters.render_dialog_buttons", _fake_render)

    get_available_trial = AsyncMock(spec=GetAvailableTrialUseCase)
    get_available_trial.return_value = MagicMock(is_trial_available=False, plan=None)

    captured_kwargs: dict[str, object] = {}

    def _fake_get(key: str, **kwargs: object) -> str:
        if key == "msg-main-menu":
            captured_kwargs.update(kwargs)
        return key

    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value = MagicMock(get=_fake_get)

    await menu_getter.__dishka_orig_func__(
        dialog_manager=dialog_manager,
        config=config,
        banner_repository=banner_repository,
        subscription_repository=subscription_repository,
        get_available_trial=get_available_trial,
        i18n=i18n,
        dialog_config_cache=fake_cache,
    )

    assert captured_kwargs.get("name") == "Test"


async def test_device_confirm_getter_routes_message_text_through_resolve_variable_kwargs(
    monkeypatch,
) -> None:
    # An admin-saved { $name } in msg-menu-devices-confirm-delete must resolve to
    # its default instead of crashing the window -- so the getter has to supply
    # every registered catalog variable, not a bare runner.get().
    assert "name" in catalog.variable_keys()

    dialog_manager = MagicMock()
    dialog_manager.middleware_data = {USER_KEY: MagicMock(id=1, language=Locale.EN)}

    async def _fake_render(*args, **kwargs):
        return []

    monkeypatch.setattr("app.telegram.routers.menu.getters.render_dialog_buttons", _fake_render)

    captured_kwargs: dict[str, object] = {}

    def _fake_get(key: str, **kwargs: object) -> str:
        captured_kwargs.update(kwargs)
        return key

    i18n = MagicMock()
    i18n.get_translator_by_locale.return_value = MagicMock(get=_fake_get)

    await device_confirm_delete_getter.__dishka_orig_func__(
        dialog_manager=dialog_manager,
        i18n=i18n,
        dialog_config_cache=MagicMock(),
    )

    assert "name" in captured_kwargs
