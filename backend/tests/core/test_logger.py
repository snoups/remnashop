import logging

from loguru import logger

from app.core.logger import InterceptHandler


def test_intercept_handler_masks_bot_token_in_url() -> None:
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}")
    try:
        record = logging.LogRecord(
            name="httpx",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="HTTP Request: %s %s",
            args=("POST", "https://api.telegram.org/bot123456:AAH-dummy_Token/setMyCommands"),
            exc_info=None,
        )
        InterceptHandler().emit(record)
    finally:
        logger.remove(sink_id)

    assert messages == ["HTTP Request: POST https://api.telegram.org/bot<redacted>/setMyCommands\n"]
