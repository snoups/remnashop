import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.enums import DialogFlow, Locale
from app.core.utils.telegram_text import TELEGRAM_CAPTION_LIMIT
from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.telegram.dialogs.config_cache import DialogConfigCache
from app.telegram.dialogs.rendering import (
    UNAVAILABLE_BUTTONS_KEY,
    TrustedHtml,
    _resolve_variables,
    banner_within_caption,
    fits_caption,
    render_dialog_buttons,
    render_window_text,
    resolve_variable_kwargs,
)
from app.telegram.i18n import build_translator_hub

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
    catalog.register_variable(
        "subscription.url", lambda data: data.get("subscription_url", ""), category="user"
    )
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
    # a typo in a `${variable}` token renders "" instead of crashing the window
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
    catalog.register_variable("name", lambda data: data.get("name", ""), category="user")
    kwargs = resolve_variable_kwargs({"name": "Иван", "subscription_url": "https://x"})
    assert kwargs["name"] == "Иван"
    assert kwargs["subscription.url"] == "https://x"


def test_resolve_variable_kwargs_uses_resolver_default_for_missing_data() -> None:
    catalog.register_variable("name", lambda data: data.get("name", ""), category="user")
    kwargs = resolve_variable_kwargs({})
    assert kwargs["name"] == ""


async def test_unknown_visibility_condition_hides_button(
    session, dialog_repository: DialogRepository
) -> None:
    # a typo in visibility_condition hides the button instead of crashing the window
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


class _TemplateRunner:
    # substitutes kwargs the way Fluent fills `{ $x }` placeables
    def __init__(self, template: str) -> None:
        self._template = template

    def get(self, key: str, **kwargs: object) -> str:
        text = self._template
        for name, value in kwargs.items():
            text = text.replace(f"{{ ${name} }}", str(value))
        return text


def _runner(template: str) -> _TemplateRunner:
    return _TemplateRunner(template)


def test_values_are_escaped_template_is_not() -> None:
    out = render_window_text(_runner("<b>{ $name }</b>"), "k", name="<i>&")
    assert out == "<b>&lt;i&gt;&amp;</b>"


def test_trusted_html_is_not_escaped() -> None:
    assert (
        render_window_text(_runner("{ $block }"), "k", block=TrustedHtml("<b>x</b>")) == "<b>x</b>"
    )


def test_line_with_empty_variable_is_dropped() -> None:
    assert render_window_text(_runner("a\nskidka { $d }%\nb"), "k", d="") == "a\nb"


def test_line_with_none_variable_is_dropped() -> None:
    assert render_window_text(_runner("a\nskidka { $d }%\nb"), "k", d=None) == "a\nb"


def test_dropped_line_keeps_its_tags() -> None:
    tpl = "<b>P</b>:\n<blockquote>• id { $id }\n• name { $n }\n• d { $d }%</blockquote>"
    out = render_window_text(_runner(tpl), "k", id="", n="Bob", d="")
    assert out == "<b>P</b>:\n<blockquote>• name Bob</blockquote>"


def test_dropped_line_with_a_closed_tag_still_closes_the_quote_on_the_line_above() -> None:
    tpl = "<blockquote>• n { $n }\n• <b>d</b>: { $d }%</blockquote>\n\nnext"
    out = render_window_text(_runner(tpl), "k", n="Bob", d="")
    assert out == "<blockquote>• n Bob</blockquote>\n\nnext"


def test_dropped_first_and_last_lines_keep_their_tags() -> None:
    tpl = "<blockquote>{ $a }\nmid\n{ $b }</blockquote>"
    assert render_window_text(_runner(tpl), "k", a="", b="") == "<blockquote>mid</blockquote>"


def test_blank_lines_collapse() -> None:
    assert render_window_text(_runner("a\n\n{ $x }\n\nb"), "k", x="") == "a\n\nb"


def test_edge_blank_lines_are_trimmed() -> None:
    assert render_window_text(_runner("{ $x }\n\na\n\n"), "k", x="") == "a"


def test_int_values_pass_through() -> None:
    assert render_window_text(_runner("n={ $n }"), "k", n=0) == "n=0"


def test_multiline_block_line_with_empty_variable_is_dropped_whole() -> None:
    block = TrustedHtml("<blockquote>l1\nl2</blockquote>")
    tpl = "a\n{ $blk } { $x }\nb"
    assert render_window_text(_runner(tpl), "k", blk=block, x="") == "a\nb"


def test_multiline_block_keeps_its_own_blank_line() -> None:
    block = TrustedHtml("<blockquote>l1\n\n\nl2</blockquote>")
    assert render_window_text(_runner("{ $blk }"), "k", blk=block) == block


def test_real_fluent_drops_multiline_block_line_without_orphan_bidi_marks() -> None:
    hub = build_translator_hub(
        [Locale.EN], {Locale.EN: "k = a\n    { $blk } { $x }\n    b\n"}, Locale.EN
    )
    runner = hub.get_translator_by_locale(Locale.EN.value)
    block = TrustedHtml("<blockquote>l1\nl2</blockquote>")
    out = render_window_text(runner, "k", blk=block, x="")
    assert out == "a\nb"
    shown = render_window_text(runner, "k", blk=block, x="y")
    assert "l1\nl2" in shown
    assert shown.count("\u2068") == shown.count("\u2069")


def test_fits_caption_counts_text_without_tags() -> None:
    assert fits_caption("<b>" + "x" * TELEGRAM_CAPTION_LIMIT + "</b>")
    assert not fits_caption("x" * (TELEGRAM_CAPTION_LIMIT + 1))


def test_banner_within_caption_drops_banner_for_long_text() -> None:
    assert banner_within_caption("banner", "short") == "banner"
    assert banner_within_caption("banner", "x" * (TELEGRAM_CAPTION_LIMIT + 1)) is None
    assert banner_within_caption(None, "short") is None


def test_render_window_text_ignores_a_malformed_emoji_marker() -> None:
    runner = _StubRunner("[\U0001f381](emoji:not-a-number)")
    assert render_window_text(runner, "k") == "[\U0001f381](emoji:not-a-number)"


def test_text_without_any_visible_line_left_keeps_its_lines() -> None:
    assert render_window_text(_runner("Your link: { $u }"), "k", u="") == "Your link: "


def test_quote_without_any_visible_line_left_keeps_its_lines() -> None:
    tpl = "<blockquote>{ $a }\n{ $b }</blockquote>"
    assert render_window_text(_runner(tpl), "k", a="", b=None) == "<blockquote>\n</blockquote>"


def test_a_value_cannot_form_premium_emoji_markup() -> None:
    out = render_window_text(_runner("Hi { $name }"), "k", name="[x](emoji:123)")

    assert "tg-emoji" not in out
    assert out == "Hi &#91;x](emoji:123)"


def test_quotes_in_a_value_cannot_close_an_attribute() -> None:
    out = render_window_text(_runner('<a href="tg://x?n={ $name }">x</a>'), "k", name='a" b')

    assert out == '<a href="tg://x?n=a&quot; b">x</a>'


def test_a_variable_inside_a_url_is_encoded() -> None:
    catalog.register_variable("user_name", lambda data: data.get("name", ""), category="user")
    data = {"name": "a&b=c d", "subscription_url": "https://example.com/sub"}

    assert _resolve_variables("https://t.me/x?text=${user_name}", data) == (
        "https://t.me/x?text=a%26b%3Dc%20d"
    )
    # a variable that is the whole URL stays as it is
    assert _resolve_variables("${subscription.url}", data) == "https://example.com/sub"


def test_quote_tags_on_their_own_lines_add_no_empty_lines() -> None:
    tpl = "<b>P</b>:\n<blockquote>\n• id { $id }\n• d { $d }%\n</blockquote>\n\nnext"
    out = render_window_text(_runner(tpl), "k", id="7", d="")
    assert out == "<b>P</b>:\n<blockquote>• id 7</blockquote>\n\nnext"


async def test_hides_button_of_an_unavailable_action_despite_its_condition(
    session, dialog_repository: DialogRepository
) -> None:
    cache = await _cache(session, dialog_repository)
    rows = await render_dialog_buttons(
        "menu.main",
        cache,
        _FakeRunner(),
        {
            "trial_available": True,
            "subscription_url": "https://x",
            UNAVAILABLE_BUTTONS_KEY: {"get_trial"},
        },
    )
    texts = [b["text"] for row in rows for b in row]
    assert "[btn-menu.trial]" not in texts
    assert "[btn-menu.connect]" in texts
