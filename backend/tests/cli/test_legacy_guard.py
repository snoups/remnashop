from app.cli.legacy_guard import legacy_guard_message


def test_guard_message_for_legacy_revision() -> None:
    message = legacy_guard_message("0039")
    assert message is not None
    assert "docker compose run --rm remnashop cli" in message


def test_guard_silent_for_fresh_and_current() -> None:
    assert legacy_guard_message(None) is None
    assert legacy_guard_message("current") is None
    assert legacy_guard_message("0047") is None
