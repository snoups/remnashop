from unittest.mock import MagicMock

from aiogram.fsm.storage.memory import SimpleEventIsolation

from app.telegram.dispatcher import get_dispatcher


def test_dispatcher_runs_a_users_updates_one_at_a_time() -> None:
    config = MagicMock()
    config.redis.dsn = "redis://localhost:6379/0"

    dispatcher = get_dispatcher(config)

    assert isinstance(dispatcher.fsm.events_isolation, SimpleEventIsolation)
