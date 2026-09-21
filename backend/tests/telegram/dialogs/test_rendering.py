import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.enums import DialogFlow
from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.rendering import (
    render_dialog_buttons,
    render_window_text,
    resolve_variable_kwargs,
)

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
            "visibility_condition": "trial_available",
            "style": None,
            "icon_custom_emoji_id": None,
            "is_hidden": False,
        },
        {
            "key": "connect",
            "text_key": "btn-menu.connect",
            "row": 1,
            "column": 0,
            "link_type": "url",
            "action_key": None,
            "target_window_key": None,
            "url_value": "${subscription.url}",
            "visibility_condition": None,
            "style": None,
            "icon_custom_emoji_id": None,
            "is_hidden": False,
        },
    ],
}


class _FakeRunner:
    def get(self, key: str, **kwargs: object) -> str:
        return f"[{key}]"


@pytest.fixture(autouse=True)
def _catalog():
    catalog._reset_for_tests()
    catalog.register_condition("trial_available", lambda data: bool(data.get("trial_available")))
    catalog.register_variable("subscription.url", lambda data: data.get("subscription_url", ""))
    yield
    catalog._reset_for_tests()


async def _cache(session, dialog_repository: DialogRepository) -> DialogConfigCache:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, "menu", _SNAPSHOT)
    session_maker = async_sessionmaker(
        bind=session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    return DialogConfigCache(session_maker)


async def test_hides_button_when_condition_false(
    session, dialog_repository: DialogRepository
) -> None:
    cache = await _cache(session, dialog_repository)
    rows = await render_dialog_buttons(
        "menu.main",
        cache,
        _FakeRunner(),
        {"trial_available": False, "subscription_url": "https://x"},
    )
    texts = [b["text"] for row in rows for b in row]
    assert "[btn-menu.trial]" not in texts
    assert "[btn-menu.connect]" in texts


async def test_shows_button_when_condition_true(
    session, dialog_repository: DialogRepository
) -> None:
    cache = await _cache(session, dialog_repository)
    rows = await render_dialog_buttons(
        "menu.main",
        cache,
        _FakeRunner(),
        {"trial_available": True, "subscription_url": "https://x"},
    )
    texts = [b["text"] for row in rows for b in row]
    assert "[btn-menu.trial]" in texts


async def test_substitutes_variable_in_url(session, dialog_repository: DialogRepository) -> None:
    cache = await _cache(session, dialog_repository)
    rows = await render_dialog_buttons(
        "menu.main",
        cache,
        _FakeRunner(),
        {"trial_available": True, "subscription_url": "https://example.com/sub"},
    )
    connect = next(b for row in rows for b in row if b["text"] == "[btn-menu.connect]")
    assert connect["url_value"] == "https://example.com/sub"


async def test_rows_are_ordered(session, dialog_repository: DialogRepository) -> None:
    cache = await _cache(session, dialog_repository)
    rows = await render_dialog_buttons(
        "menu.main", cache, _FakeRunner(), {"trial_available": True, "subscription_url": "x"}
    )
    assert len(rows) == 2  # row 0 (trial) and row 1 (connect), each one button


async def test_unknown_variable_token_resolves_to_empty_string(
    session, dialog_repository: DialogRepository
) -> None:
    # An admin typo in a `${variable}` token must not crash the whole window for
    # every user -- fall back to "" rather than propagating catalog.get_variable's
    # KeyError.
    await dialog_repository.upsert_seed(
        "menu.main",
        DialogFlow.MENU,
        "menu",
        {
            "banner_name": "menu",
            "buttons": [
                {
                    "key": "connect",
                    "text_key": "btn-menu.connect",
                    "row": 0,
                    "column": 0,
                    "link_type": "url",
                    "action_key": None,
                    "target_window_key": None,
                    "url_value": "${no.such.variable}",
                    "visibility_condition": None,
                    "style": None,
                    "icon_custom_emoji_id": None,
                    "is_hidden": False,
                }
            ],
        },
    )
    session_maker = async_sessionmaker(
        bind=session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    cache = DialogConfigCache(session_maker)
    rows = await render_dialog_buttons("menu.main", cache, _FakeRunner(), {})
    assert rows[0][0]["url_value"] == ""


def test_resolve_variable_kwargs_reflects_all_registered_variables() -> None:
    catalog.register_variable("name", lambda data: data.get("name", ""))
    kwargs = resolve_variable_kwargs({"name": "Иван", "subscription_url": "https://x"})
    assert kwargs["name"] == "Иван"
    assert kwargs["subscription.url"] == "https://x"


def test_resolve_variable_kwargs_uses_resolver_default_for_missing_data() -> None:
    catalog.register_variable("name", lambda data: data.get("name", ""))
    kwargs = resolve_variable_kwargs({})
    assert kwargs["name"] == ""


async def test_unknown_visibility_condition_hides_button(
    session, dialog_repository: DialogRepository
) -> None:
    # Same failure mode as the unknown-variable-token bug: an admin typo in
    # visibility_condition must not crash the whole window via catalog.get_condition's
    # KeyError -- hide the button (fail-safe) instead.
    await dialog_repository.upsert_seed(
        "menu.main",
        DialogFlow.MENU,
        "menu",
        {
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
                    "visibility_condition": "no_such_condition",
                    "style": None,
                    "icon_custom_emoji_id": None,
                    "is_hidden": False,
                }
            ],
        },
    )
    session_maker = async_sessionmaker(
        bind=session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    cache = DialogConfigCache(session_maker)
    rows = await render_dialog_buttons("menu.main", cache, _FakeRunner(), {})
    assert rows == []


class _StubRunner:
    def __init__(self, value: str) -> None:
        self._value = value

    def get(self, key: str, **kwargs: object) -> str:
        return self._value


def test_render_window_text_turns_markup_into_a_tg_emoji_tag() -> None:
    runner = _StubRunner("\U0001f381 Hello")
    assert render_window_text(runner, "k") == "\U0001f381 Hello"

    runner = _StubRunner("[\U0001f381](emoji:5386587088873331829) Hello")
    assert render_window_text(runner, "k") == (
        '<tg-emoji emoji-id="5386587088873331829">\U0001f381</tg-emoji> Hello'
    )


def test_render_window_text_escapes_everything_else() -> None:
    # The window renders as HTML so <tg-emoji> works, which makes any unescaped
    # text -- a user's own display name among it -- an injection point.
    runner = _StubRunner('<a href="http://evil">click</a> & <b>bold</b>')
    assert render_window_text(runner, "k") == (
        '&lt;a href="http://evil"&gt;click&lt;/a&gt; &amp; &lt;b&gt;bold&lt;/b&gt;'
    )


def test_render_window_text_ignores_a_malformed_emoji_marker() -> None:
    runner = _StubRunner("[\U0001f381](emoji:not-a-number)")
    assert render_window_text(runner, "k") == "[\U0001f381](emoji:not-a-number)"
