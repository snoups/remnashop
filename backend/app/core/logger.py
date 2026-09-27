import atexit
import inspect
import logging
import sys
from collections import deque
from typing import Final, Union

from loguru import logger
from redis import Redis, RedisError

from app.core.config import AppConfig
from app.core.constants import LOG_DIR

LOG_BUFFER_CAPACITY: Final[int] = 200
REDIS_LOG_CAPACITY: Final[int] = 500
REDIS_LOG_TIMEOUT_S: Final[float] = 2.0
LOG_FILENAME: Final[str] = "remnashop.log"
LOG_ENCODING: Final[str] = "utf-8"
LOG_FORMAT: Final[str] = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
)


class LogBuffer:
    def __init__(self, capacity: int = LOG_BUFFER_CAPACITY) -> None:
        self._records: deque[str] = deque(maxlen=capacity)

    def write(self, message: str) -> None:
        self._records.append(message.rstrip())

    def get_context(self, lines: int = 100) -> str:
        records = list(self._records)
        return "\n".join(records[-lines:])


log_buffer = LogBuffer()


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

    # diagnose=False on every sink: loguru's default annotates each traceback
    # frame with the repr of that frame's variables. On a request path those
    # hold the caller's bearer credential; on the asyncpg path, the database
    # password. Neither reaches the log through an application DTO, so schema
    # changes alone would not close it.
    logger.add(
        sink=sys.stderr,
        level=config.log.level,
        format=LOG_FORMAT,
        colorize=True,
        diagnose=False,
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
            diagnose=False,
        )

    logger.add(
        sink=log_buffer.write,
        level=config.log.level,
        format=LOG_FORMAT,
        colorize=False,
        diagnose=False,
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


def add_redis_sink(config: AppConfig, key: str) -> None:
    # Survives the process itself, so the dashboard can show why it failed to start.
    # Sync client on loguru's enqueue thread -- never blocks the event loop.
    redis = Redis.from_url(config.redis.dsn, socket_timeout=REDIS_LOG_TIMEOUT_S)

    def write(message: str) -> None:
        try:
            with redis.pipeline() as pipe:
                pipe.rpush(key, message.rstrip())
                pipe.ltrim(key, -REDIS_LOG_CAPACITY, -1)
                pipe.execute()
        except RedisError:
            pass  # stderr/file sinks still have it

    logger.add(
        sink=write,
        level=config.log.level,
        format=LOG_FORMAT,
        colorize=False,
        diagnose=False,
        enqueue=True,
    )
    # otherwise a crash's last lines -- the ones worth seeing -- die in the queue
    atexit.register(logger.complete)
