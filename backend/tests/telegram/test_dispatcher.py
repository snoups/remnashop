from unittest.mock import MagicMock

from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisStorage

from app.telegram.dispatcher import get_dispatcher


def test_dispatcher_runs_a_users_updates_one_at_a_time() -> None:
    config = MagicMock()
    config.redis.dsn = "redis://localhost:6379/0"

    dispatcher = get_dispatcher(config)

    assert isinstance(dispatcher.fsm.events_isolation, SimpleEventIsolation)


def test_storage_keys_dialog_stacks_by_destiny() -> None:
    config = MagicMock()
    config.redis.dsn = "redis://localhost:6379/0"

    storage = get_dispatcher(config).storage
    assert isinstance(storage, RedisStorage)

    # aiogram-dialog stores its stack and contexts under their own destiny
    key = StorageKey(bot_id=1, chat_id=2, user_id=2, destiny="aiogd:stack:")
    assert "aiogd:stack:" in storage.key_builder.build(key, "data")


def test_workflow_data_does_not_shadow_injected_getter_params() -> None:
    config = MagicMock()
    config.redis.dsn = "redis://localhost:6379/0"

    # dialog getters receive workflow data as kwargs; a "config" key collides with
    # their config: FromDishka[AppConfig] parameter
    assert "config" not in get_dispatcher(config).workflow_data
