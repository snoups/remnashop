import atexit
import inspect
import logging
import re
import sys
from collections import deque
from typing import TYPE_CHECKING, Final, Union

from loguru import logger
from redis import Redis, RedisError

from app.core.config import AppConfig
from app.core.constants import LOG_DIR

if TYPE_CHECKING:
    from loguru import Record

LOG_BUFFER_CAPACITY: Final[int] = 200
REDIS_LOG_CAPACITY: Final[int] = 500
REDIS_LOG_TIMEOUT_S: Final[float] = 2.0
LOG_ENCODING: Final[str] = "utf-8"
# Bot API calls carry the token in the URL path, and httpx logs every request URL at INFO
_BOT_TOKEN_IN_URL: Final[re.Pattern[str]] = re.compile(r"/bot\d+:[\w-]+")
_BOT_TOKEN_MASK: Final[str] = "/bot<redacted>"
# payment status checks sign their query; the hash lets a weak password be guessed offline
_SIGNATURE_IN_QUERY: Final[re.Pattern[str]] = re.compile(r"(?i)([?&]signature=)[^&\s]+")
_SIGNATURE_MASK: Final[str] = r"\1<redacted>"
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


def _mask_secrets(text: str) -> str:
    return _SIGNATURE_IN_QUERY.sub(_SIGNATURE_MASK, _BOT_TOKEN_IN_URL.sub(_BOT_TOKEN_MASK, text))


class RedactedError(Exception):
    """Stands in for a logged exception whose text carried a secret."""


def redact_exception(record: "Record") -> None:
    # an HTTP client error repeats the request URL, and a Bot API URL holds the token
    exception = record["exception"]
    if exception is None or exception.type is None or exception.value is None:
        return
    text = str(exception.value)
    masked = _mask_secrets(text)
    if masked != text:
        record["exception"] = exception._replace(
            type=RedactedError, value=RedactedError(f"{exception.type.__name__}: {masked}")
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

        message = _mask_secrets(record.getMessage())
        logger.opt(depth=depth, exception=record.exc_info).log(level, message)


def setup_logger(config: AppConfig, process: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.configure(patcher=redact_exception)

    # diagnose=False on every sink: loguru would print each traceback frame's
    # locals, the bearer credential on a request path, the DB password in asyncpg
    logger.add(
        sink=sys.stderr,
        level=config.log.level,
        format=LOG_FORMAT,
        colorize=True,
        diagnose=False,
    )

    if config.log.to_file:
        logger.add(
            # one file per process: two processes rotating one file clobber each other
            sink=LOG_DIR / f"remnashop-{process}.log",
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
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers = [intercept_handler]
        uvicorn_logger.propagate = False  # parent/root carry the same handler


def add_redis_sink(config: AppConfig, key: str) -> None:
    # Survives the process itself, so the dashboard can show why it failed to start.
    # sync client on loguru's enqueue thread, never blocks the event loop
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
    # otherwise a crash's last lines, the ones worth seeing, die in the queue
    atexit.register(logger.complete)
