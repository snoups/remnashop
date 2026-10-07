from pathlib import Path

import pytest
from fluent.syntax import FluentParser
from fluent.syntax.ast import Message

from app.core.config import AppConfig
from app.core.enums import Locale
from app.modules.notifications import NOTIFICATION_GROUPS
from app.modules.notifications.render import (
    TEST_EVENT_TYPE,
    NotificationRenderer,
    message_id,
    notification_args,
)

SEEDED_LOCALES = (Locale.EN, Locale.RU)
FTL = "ntf-login-failed = Login { $login }\n    .title = Login failed\n"


def _messages(path: Path) -> dict[str, Message]:
    resource = FluentParser().parse(path.read_text())
    return {e.id.name: e for e in resource.body if isinstance(e, Message)}


@pytest.mark.parametrize("locale", SEEDED_LOCALES)
def test_every_notification_type_has_a_template_with_a_title(
    config: AppConfig, locale: Locale
) -> None:
    messages = _messages(config.translations_dir / locale.value / "notifications.ftl")
    event_types = [*frozenset().union(*NOTIFICATION_GROUPS.values()), TEST_EVENT_TYPE]
    for event_type in event_types:
        key = message_id(event_type)
        assert key in messages, f"{key} missing in {locale}"
        assert messages[key].value is not None
        assert any(a.id.name == "title" for a in messages[key].attributes)


def test_message_id_is_kebab_without_event_suffix() -> None:
    assert message_id("LoginFailedEvent") == "ntf-login-failed"
    assert message_id("OAuthLoginFailedEvent") == "ntf-oauth-login-failed"
    assert message_id(TEST_EVENT_TYPE) == "ntf-test"


def test_args_flatten_user_snapshots_and_keep_scalars() -> None:
    args = notification_args(
        {"user": {"login": None, "username": "bob", "name": "Bob"}, "amount": "500", "flag": True},
        "1.2.3.4",
    )
    assert args == {"user": "@bob", "amount": "500", "ip": "1.2.3.4"}


def test_render_falls_back_to_default_locale_then_to_event_type() -> None:
    renderer = NotificationRenderer({Locale.EN: FTL}, default_locale=Locale.EN)
    assert renderer.render(Locale.DE, "LoginFailedEvent", {"login": "x"}) == (
        "Login failed",
        "Login x",
    )
    assert renderer.render(Locale.EN, "BackupFailedEvent", {}) == ("BackupFailedEvent", "")


def test_render_survives_a_missing_variable() -> None:
    renderer = NotificationRenderer({Locale.EN: FTL}, default_locale=Locale.EN)
    title, body = renderer.render(Locale.EN, "LoginFailedEvent", {})
    assert title == "Login failed"
    assert body


def test_render_falls_through_a_message_without_title() -> None:
    renderer = NotificationRenderer(
        {Locale.RU: "ntf-login-failed = Вход { $login }\n", Locale.EN: FTL},
        default_locale=Locale.EN,
    )
    assert renderer.render(Locale.RU, "LoginFailedEvent", {"login": "x"}) == (
        "Login failed",
        "Login x",
    )
    body_only = NotificationRenderer({Locale.EN: "ntf-login-failed = x\n"}, Locale.EN)
    assert body_only.render(Locale.EN, "LoginFailedEvent", {}) == ("LoginFailedEvent", "")


def test_missing_ip_reads_as_a_dash() -> None:
    assert notification_args({}, None) == {"ip": "—"}
