from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.emoji_packs.dto import EmojiPackDto
from app.modules.emoji_packs.repository import EmojiPackRepository
from app.modules.emoji_packs.telegram_api import fetch_emoji_pack, parse_set_name
from app.modules.settings import SettingsRepository


class ImportEmojiPackUseCase(UseCase[str, EmojiPackDto]):
    required_permission = Permission.EMOJI_PACKS_IMPORT

    def __init__(
        self,
        emoji_pack_repository: EmojiPackRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
    ) -> None:
        self._emoji_pack_repository = emoji_pack_repository
        self._settings_repository = settings_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: str) -> EmojiPackDto:
        try:
            set_name = parse_set_name(data)
        except ValueError as err:
            raise ValidationError(str(err), code=ErrorCode.EMOJI_PACK_NAME_INVALID) from None

        async with self._uow:
            bot_settings = await self._settings_repository.get_bot_settings()
        if bot_settings.token is None:
            # Reading a pack is a Bot API call, so there is nothing to do until
            # someone has set the token on the dashboard.
            raise ValidationError(
                "Set the bot token before importing an emoji pack",
                code=ErrorCode.EMOJI_PACK_BOT_TOKEN_MISSING,
            )

        try:
            fetched = await fetch_emoji_pack(bot_settings.token.get_secret_value(), set_name)
        except ValueError as err:
            raise ValidationError(str(err), code=ErrorCode.EMOJI_PACK_FETCH_FAILED) from None

        async with self._uow:
            return await self._emoji_pack_repository.upsert(fetched)
