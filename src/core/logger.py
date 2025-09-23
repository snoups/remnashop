import inspect
import logging
import sys
from pathlib import Path
from typing import Final
from zipfile import ZipFile

from loguru import logger

from src.core.constants import LOG_DIR

LOG_FILENAME: Final[str] = "bot.log"
LOG_LEVEL: Final[str] = "DEBUG"
LOG_ROTATION: Final[str] = "00:00"
LOG_COMPRESSION: Final[str] = "zip"
LOG_RETENTION: Final[str] = "7 days"
LOG_ENCODING: Final[str] = "utf-8"
LOG_FORMAT: Final[str] = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists.
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
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


def compress_log_file(filepath: str) -> None:
    log_file = Path(filepath)
    filename_stem = log_file.stem
    suffix_candidate = filename_stem.rpartition("_")[-1]

    # Remove trailing digit suffix if present (e.g. "_12345")
    if suffix_candidate.isdigit():
        filename_stem = filename_stem[: -(len(suffix_candidate) + 1)]

    original_extension = log_file.suffix
    archive_filename = f"{filename_stem}{original_extension}.{LOG_COMPRESSION}"
    archive_path = log_file.with_name(archive_filename)

    with ZipFile(archive_path, "w") as archive:
        archive.write(log_file, arcname=LOG_FILENAME)

    log_file.unlink()


def setup_logger() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()

    logger.add(
        sink=sys.stderr,
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        colorize=True,
    )

    logger.add(
        sink=LOG_DIR / LOG_FILENAME,
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        compression=compress_log_file,
        encoding=LOG_ENCODING,
    )

    intercept_handler = InterceptHandler()
    logging.basicConfig(handlers=[intercept_handler], level=logging.INFO, force=True)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "httpx"):
        logging.getLogger(logger_name).handlers = [intercept_handler]
        logging.getLogger(logger_name).propagate = False
