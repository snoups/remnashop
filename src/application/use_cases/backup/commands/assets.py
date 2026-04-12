import shutil
import tempfile
from pathlib import Path

from loguru import logger

from src.application.common import Interactor, Notifier
from src.application.common.policy import Permission
from src.application.dto import MediaDescriptorDto, MessagePayloadDto, UserDto
from src.core.constants import DATETIME_FILE_FORMAT
from src.core.enums import MediaType
from src.core.utils.time import datetime_now

from .dump import CreateAssetsDump


class BackupAssets(Interactor[None, None]):
    required_permission = Permission.SETTINGS_BACKUP

    def __init__(self, notifier: Notifier, create_assets_dump: CreateAssetsDump) -> None:
        self.notifier = notifier
        self.create_assets_dump = create_assets_dump

    async def _execute(self, actor: UserDto, data: None) -> None:
        await self.notifier.notify_user(actor, i18n_key="ntf-backup.assets-started")

        tmp_dir = Path(tempfile.mkdtemp())
        try:
            timestamp = datetime_now().strftime(DATETIME_FILE_FORMAT)
            zip_path = tmp_dir / f"assets_backup_{timestamp}"

            await self.create_assets_dump.system(zip_path)
            zip_file = Path(str(zip_path) + ".zip")

            await self.notifier.notify_user(
                user=actor,
                payload=MessagePayloadDto(
                    i18n_key="",
                    media=MediaDescriptorDto(
                        kind="fs",
                        value=str(zip_file),
                        filename=zip_file.name,
                    ),
                    media_type=MediaType.DOCUMENT,
                    delete_after=None,
                    disable_default_markup=False,
                ),
            )
            logger.info(f"{actor.log} Assets backup sent: {zip_file.name}")
        except Exception as e:
            logger.exception(f"{actor.log} Failed to create assets backup: {e}")
            await self.notifier.notify_user(actor, i18n_key="ntf-backup.error")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
