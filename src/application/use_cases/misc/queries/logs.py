from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from src.application.common import Interactor
from src.application.common.policy import Permission
from src.application.dto import UserDto
from src.core.config import AppConfig
from src.core.constants import DATETIME_FILE_FORMAT, LOG_DIR
from src.core.exceptions import FileNotFoundError, LogsToFileDisabledError
from src.core.logger import LOG_FILENAME
from src.core.utils.time import datetime_now


@dataclass(frozen=True)
class GetLogsResultDto:
    path: Path
    display_name: str


class GetLogs(Interactor[None, GetLogsResultDto]):
    required_permission = Permission.REMNASHOP_LOGS

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def _execute(self, actor: UserDto, data: None) -> GetLogsResultDto:
        if not self.config.log.to_file:
            logger.warning(f"User '{actor.telegram_id}' requested logs, but to_file is disabled")
            raise LogsToFileDisabledError()

        log_path = LOG_DIR / LOG_FILENAME

        if not log_path.exists():
            logger.error(f"Log file not found at '{log_path}'")
            raise FileNotFoundError()

        timestamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
        display_name = f"{timestamp}.log"

        logger.info(f"Log file '{log_path}' prepared for user '{actor.telegram_id}'")
        return GetLogsResultDto(path=log_path, display_name=display_name)
