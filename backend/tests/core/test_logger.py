import logging
import sys
from pathlib import Path

import pytest
from loguru import logger

import app.core.logger as logger_module
from app.core.config import AppConfig
from app.core.logger import InterceptHandler, setup_logger


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


def test_each_process_writes_its_own_log_file(
    config: AppConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(logger_module, "LOG_DIR", tmp_path)
    root_handlers = logging.getLogger().handlers[:]
    log_config = config.log.model_copy(update={"to_file": True})
    try:
        setup_logger(config.model_copy(update={"log": log_config}), "api")
        logger.info("x")
    finally:
        logger.remove()
        logger.add(sys.stderr)
        logging.getLogger().handlers = root_handlers

    assert [p.name for p in tmp_path.iterdir()] == ["remnashop-api.log"]
