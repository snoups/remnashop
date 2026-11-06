from app.cli.legacy.schema import new_chain_revisions
from app.cli.legacy_guard import StartAction, start_action

_NEW: frozenset[str] = frozenset({"current", "123456789012"})


def test_legacy_revision_is_migrated() -> None:
    assert start_action("0001", _NEW) is StartAction.MIGRATE
    assert start_action("0039", _NEW) is StartAction.MIGRATE
    assert start_action("0046", _NEW) is StartAction.MIGRATE


def test_fresh_and_new_chain_revisions_start() -> None:
    assert start_action(None, _NEW) is StartAction.START
    assert start_action("current", _NEW) is StartAction.START
    assert start_action("123456789012", _NEW) is StartAction.START
    assert start_action("a1b2c3", _NEW) is StartAction.START


def test_newer_legacy_revision_is_refused() -> None:
    assert start_action("0047", _NEW) is StartAction.REFUSE


def test_new_chain_contains_the_shipped_revision() -> None:
    assert "current" in new_chain_revisions()
