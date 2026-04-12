from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.types import Document
from loguru import logger

from src.application.common import Interactor
from src.application.common.policy import Permission
from src.application.dto import UserDto
from src.application.use_cases.importer.dto import ExportedUserDto
from src.application.use_cases.importer.queries.filters import SplitExportedUsers
from src.application.use_cases.importer.queries.xui import ExportUsersFromXui


@dataclass(frozen=True)
class ProcessImportFileResultDto:
    all_users: list[ExportedUserDto]
    active_users: list[ExportedUserDto]
    expired_users: list[ExportedUserDto]


class ProcessImportFile(Interactor[Document, ProcessImportFileResultDto]):
    required_permission = Permission.IMPORTER

    def __init__(
        self,
        export_users_from_xui: ExportUsersFromXui,
        split_exported_users: SplitExportedUsers,
        bot: Bot,
    ) -> None:
        self.export_users_from_xui = export_users_from_xui
        self.split_exported_users = split_exported_users
        self.bot = bot

    async def _execute(
        self,
        actor: UserDto,
        document: Document,
    ) -> ProcessImportFileResultDto:
        local_file_path = Path(f"/tmp/{document.file_name}")
        file = await self.bot.get_file(document.file_id)

        if not file.file_path:
            raise ValueError(f"File path not found for document '{document.file_name}'")

        await self.bot.download_file(file.file_path, destination=local_file_path)
        logger.info(f"{actor.log} Downloaded file for processing: '{local_file_path}'")

        users = await self.export_users_from_xui(actor, local_file_path)

        if not users:
            return ProcessImportFileResultDto([], [], [])

        active, expired = await self.split_exported_users(actor, users)

        if local_file_path.exists():
            local_file_path.unlink()

        return ProcessImportFileResultDto(
            all_users=users,
            active_users=active,
            expired_users=expired,
        )
