import inspect
import logging
import sys
from typing import Final, Union

from loguru import logger

from src.core.config.app import AppConfig
from src.core.constants import LOG_DIR

LOG_FILENAME: Final[str] = "bot.log"
LOG_ENCODING: Final[str] = "utf-8"
LOG_FORMAT: Final[str] = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: Union[str, int] = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame:
            filename = frame.f_code.co_filename
            is_logging = filename == logging.__file__
            is_frozen = "importlib" in filename and "_bootstrap" in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logger(config: AppConfig) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()

    logger.add(
        sink=sys.stderr,
        level=config.log.level,
        format=LOG_FORMAT,
        colorize=True,
    )

    if config.log.to_file:
        logger.add(
            sink=LOG_DIR / LOG_FILENAME,
            level=config.log.level,
            format=LOG_FORMAT,
            rotation=config.log.rotation,
            retention=config.log.retention,
            compression=config.log.compression,
            encoding=LOG_ENCODING,
        )

    intercept_handler = InterceptHandler()
    logging.basicConfig(handlers=[intercept_handler], level=logging.INFO, force=True)

    for logger_name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
    ):
        logging.getLogger(logger_name).handlers = [intercept_handler]

    # logging.getLogger("httpx").propagate = False
    # logging.getLogger("httpx").level = logging.WARNING
