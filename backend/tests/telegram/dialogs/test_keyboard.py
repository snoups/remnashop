from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.aiogram_dialog import CONTAINER_NAME
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import AppConfig
from app.core.di.providers import get_core_providers
from app.core.enums import BannerName, ButtonLinkType, DialogFlow
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import UpdateDialogWindowDto
from app.modules.dialogs.repository import DialogRepository
from app.telegram.dialogs import state_pool
from app.telegram.dialogs.di import DialogConfigProvider
from app.telegram.dialogs.keyboard import ConfigKeyboard
from app.telegram.dialogs.state_pool import register_seed_state
from app.telegram.states import MainMenu

_SNAPSHOT = {
    "banner_name": "menu",
    "buttons": [
        {
            "key": "trial",
            "text_key": "btn-menu.trial",
            "row": 0,
            "column": 0,
            "link_type": "action",
            "action_key": "get_trial",
            "target_window_key": None,
            "url_value": None,
            "visibility_condition": None,
            "style": None,
            "icon_custom_emoji_id": None,
            "is_hidden": False,
        },
        {
            "key": "devices",
            "text_key": "btn-menu.devices",
            "row": 1,
            "column": 0,
            "link_type": "navigate",
            "action_key": None,
            "target_window_key": "menu.devices",
            "url_value": None,
            "visibility_condition": None,
            "style": None,
            "icon_custom_emoji_id": None,
            "is_hidden": False,
        },
    ],
}


class _BoundSession(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    # Overrides DatabaseProvider's own sessionmaker (bound to a fresh, unrelated
    # engine) so DialogConfigCache reads through the same connection/transaction
    # as the `session` fixture -- otherwise reload() sees none of this test's
    # unflushed-to-a-second-connection seed data. Same join_transaction_mode
    # trick as tests/telegram/dialogs/test_config_cache.py's _session_maker().
    @provide(scope=Scope.APP)
    def get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(
            bind=self._session.bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )


@pytest.fixture(autouse=True)
def _catalog_and_states():
    catalog._reset_for_tests()
    state_pool._reset_for_tests()
    yield
    catalog._reset_for_tests()
    state_pool._reset_for_tests()


async def test_render_keyboard_builds_rows_from_data() -> None:
    widget = ConfigKeyboard(window_key="menu.main")
    data = {
        "buttons": [
            [
                {
                    "id": 1,
                    "text": "Trial",
                    "style": None,
                    "icon_custom_emoji_id": None,
                    "link_type": ButtonLinkType.ACTION,
                    "action_key": "get_trial",
                    "target_window_key": None,
                    "url_value": None,
                }
            ],
            [
                {
                    "id": 2,
                    "text": "Docs",
                    "style": None,
                    "icon_custom_emoji_id": None,
                    "link_type": ButtonLinkType.URL,
                    "action_key": None,
                    "target_window_key": None,
                    "url_value": "https://example.com",
                }
            ],
        ]
    }
    keyboard = await widget._render_keyboard(data, MagicMock())
    assert len(keyboard) == 2
    assert isinstance(keyboard[0][0], InlineKeyboardButton)
    assert keyboard[0][0].text == "Trial"
    assert keyboard[1][0].url == "https://example.com"


async def test_render_keyboard_skips_url_button_with_empty_url() -> None:
    # An admin typo that makes ${variable} resolve to "" must drop the button,
    # not hand aiogram an invalid empty url.
    widget = ConfigKeyboard(window_key="menu.main")
    data = {
        "buttons": [
            [
                {
                    "id": 1,
                    "text": "Broken",
                    "style": None,
                    "icon_custom_emoji_id": None,
                    "link_type": ButtonLinkType.URL,
                    "action_key": None,
                    "target_window_key": None,
                    "url_value": "",
                }
            ]
        ]
    }
    keyboard = await widget._render_keyboard(data, MagicMock())
    assert keyboard == []


async def test_process_item_callback_dispatches_action(
    config: AppConfig, session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    window = await dialog_repository.get_by_key_or_raise("menu.main")
    trial_button = next(b for b in window.buttons if b.action_key == "get_trial")

    handler = AsyncMock()
    catalog.register_action_key("get_trial")
    catalog.bind_action_handler("get_trial", handler)

    container = make_async_container(
        *get_core_providers(),
        DialogConfigProvider(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    manager = MagicMock()
    manager.middleware_data = {CONTAINER_NAME: container}

    widget = ConfigKeyboard(window_key="menu.main")
    handled = await widget._process_item_callback(
        MagicMock(), str(trial_button.id), MagicMock(), manager
    )

    assert handled is True
    handler.assert_awaited_once()
    await container.close()


async def test_process_item_callback_dispatches_navigate(
    config: AppConfig, session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    class _S(StatesGroup):
        DEVICES = State()

    register_seed_state("menu.devices", _S.DEVICES)

    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    await dialog_repository.upsert_seed(
        "menu.devices", DialogFlow.MENU, None, {"banner_name": None, "buttons": []}
    )
    window = await dialog_repository.get_by_key_or_raise("menu.main")
    nav_button = next(b for b in window.buttons if b.link_type == ButtonLinkType.NAVIGATE)

    container = make_async_container(
        *get_core_providers(),
        DialogConfigProvider(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    manager = MagicMock()
    manager.middleware_data = {CONTAINER_NAME: container}
    manager.switch_to = AsyncMock()

    widget = ConfigKeyboard(window_key="menu.main")
    handled = await widget._process_item_callback(
        MagicMock(), str(nav_button.id), MagicMock(), manager
    )

    assert handled is True
    manager.switch_to.assert_awaited_once_with(state=_S.DEVICES)
    await container.close()


async def test_default_id_reaches_process_item_callback(
    config: AppConfig, session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    # Regression: Keyboard.callback_prefix() is falsy without a widget id, so
    # process_callback() never reaches _process_item_callback -- Task 8 constructs
    # ConfigKeyboard with no id= for every migrated window, so this has to work
    # with the default.
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    window = await dialog_repository.get_by_key_or_raise("menu.main")
    trial_button = next(b for b in window.buttons if b.action_key == "get_trial")

    handler = AsyncMock()
    catalog.register_action_key("get_trial")
    catalog.bind_action_handler("get_trial", handler)

    container = make_async_container(
        *get_core_providers(),
        DialogConfigProvider(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    manager = MagicMock()
    manager.middleware_data = {CONTAINER_NAME: container}

    widget = ConfigKeyboard(window_key="menu.main")
    assert widget.callback_prefix() is not None

    callback = MagicMock()
    callback.data = widget._item_callback_data(str(trial_button.id))
    handled = await widget.process_callback(callback, MagicMock(), manager)

    assert handled is True
    handler.assert_awaited_once()
    await container.close()


async def test_process_item_callback_unregistered_action_returns_false(
    config: AppConfig, session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    window = await dialog_repository.get_by_key_or_raise("menu.main")
    trial_button = next(b for b in window.buttons if b.action_key == "get_trial")
    # deliberately not calling catalog.register_action_key("get_trial")

    container = make_async_container(
        *get_core_providers(),
        DialogConfigProvider(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    manager = MagicMock()
    manager.middleware_data = {CONTAINER_NAME: container}

    widget = ConfigKeyboard(window_key="menu.main")
    handled = await widget._process_item_callback(
        MagicMock(), str(trial_button.id), MagicMock(), manager
    )

    assert handled is False
    await container.close()


async def test_process_item_callback_declared_but_unbound_action_returns_false(
    config: AppConfig, session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    # register_action_key/bind_action_handler split hazard: a key declared in a
    # flow's metadata (so it's in catalog.action_keys()) but never bound to a
    # handler must not reach catalog.get_action() -- that would raise KeyError
    # instead of returning False.
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    window = await dialog_repository.get_by_key_or_raise("menu.main")
    trial_button = next(b for b in window.buttons if b.action_key == "get_trial")
    catalog.register_action_key("get_trial")
    # deliberately not calling catalog.bind_action_handler("get_trial", ...)

    container = make_async_container(
        *get_core_providers(),
        DialogConfigProvider(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    manager = MagicMock()
    manager.middleware_data = {CONTAINER_NAME: container}

    widget = ConfigKeyboard(window_key="menu.main")
    handled = await widget._process_item_callback(
        MagicMock(), str(trial_button.id), MagicMock(), manager
    )

    assert handled is False
    await container.close()


async def test_process_item_callback_unknown_button_returns_false(
    config: AppConfig, session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)

    container = make_async_container(
        *get_core_providers(),
        DialogConfigProvider(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    manager = MagicMock()
    manager.middleware_data = {CONTAINER_NAME: container}

    widget = ConfigKeyboard(window_key="menu.main")
    handled = await widget._process_item_callback(MagicMock(), "999999", MagicMock(), manager)

    assert handled is False
    await container.close()


async def test_process_item_callback_unresolved_navigate_target_returns_false(
    config: AppConfig, session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    # "menu.devices" is referenced by the seed but never registered via
    # register_seed_state and isn't a CUSTOM window either.
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    window = await dialog_repository.get_by_key_or_raise("menu.main")
    nav_button = next(b for b in window.buttons if b.link_type == ButtonLinkType.NAVIGATE)

    container = make_async_container(
        *get_core_providers(),
        DialogConfigProvider(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    manager = MagicMock()
    manager.middleware_data = {CONTAINER_NAME: container}

    widget = ConfigKeyboard(window_key="menu.main")
    handled = await widget._process_item_callback(
        MagicMock(), str(nav_button.id), MagicMock(), manager
    )

    assert handled is False
    await container.close()


async def test_process_item_callback_navigate_to_disabled_window_returns_false(
    config: AppConfig, session: AsyncSession, dialog_repository: DialogRepository
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    await dialog_repository.upsert_seed(
        "menu.devices", DialogFlow.MENU, None, {"banner_name": None, "buttons": []}
    )
    await dialog_repository.update_window("menu.devices", UpdateDialogWindowDto(is_enabled=False))
    register_seed_state("menu.devices", MainMenu.DEVICES)
    window = await dialog_repository.get_by_key_or_raise("menu.main")
    nav_button = next(b for b in window.buttons if b.link_type == ButtonLinkType.NAVIGATE)

    container = make_async_container(
        *get_core_providers(),
        DialogConfigProvider(),
        _BoundSession(session),
        context={AppConfig: config},
    )
    manager = MagicMock()
    manager.middleware_data = {CONTAINER_NAME: container}

    widget = ConfigKeyboard(window_key="menu.main")
    handled = await widget._process_item_callback(
        MagicMock(), str(nav_button.id), MagicMock(), manager
    )

    assert handled is False
    await container.close()


async def test_process_item_callback_non_numeric_item_id_returns_false() -> None:
    widget = ConfigKeyboard(window_key="menu.main")
    handled = await widget._process_item_callback(
        MagicMock(), "not-a-number", MagicMock(), MagicMock()
    )

    assert handled is False
