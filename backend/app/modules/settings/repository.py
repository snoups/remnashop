from typing import Final, Optional, TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.appearance_settings import AppearanceSettings
from app.core.db.models.bot_command import BotCommand
from app.core.db.models.bot_settings import BotSettings
from app.core.db.models.oauth_settings import OAuthSettings
from app.core.db.models.shop_settings import ShopSettings
from app.core.db.partial_update import apply_partial_update
from app.core.db.singleton import get_or_create_singleton
from app.core.enums import AppearanceImageKind
from app.modules.settings.dto import (
    AppearanceSettingsDto,
    BotCommandDto,
    BotSettingsDto,
    OAuthSettingsDto,
    ShopSettingsDto,
    UpdateAppearanceSettingsDto,
    UpdateBotSettingsDto,
    UpdateOAuthSettingsDto,
    UpdateShopSettingsDto,
)

_SINGLETON_ID: Final[int] = 1
# pg_advisory_xact_lock key serializing replace_bot_commands: DELETE without
# WHERE re-evaluates its rows after a lock wait, so two concurrent
# replacements would otherwise both insert.
_BOT_COMMANDS_LOCK_KEY: Final[int] = 8221937

_SingletonRow = TypeVar(
    "_SingletonRow", BotSettings, OAuthSettings, AppearanceSettings, ShopSettings
)


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _get_or_create_singleton(self, model: type[_SingletonRow]) -> _SingletonRow:
        return await get_or_create_singleton(self.session, model, _SINGLETON_ID)

    def _to_dto(self, row: Optional[BotSettings]) -> BotSettingsDto:
        if row is None:
            return BotSettingsDto()
        return BotSettingsDto.model_validate(row, from_attributes=True)

    async def get_bot_settings(self) -> BotSettingsDto:
        row = await self.session.get(BotSettings, _SINGLETON_ID)
        return self._to_dto(row)

    async def update_bot_settings(self, data: UpdateBotSettingsDto) -> BotSettingsDto:
        row = await self._get_or_create_singleton(BotSettings)
        apply_partial_update(row, data)

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def set_bot_proxy_url(self, proxy_url: Optional[str]) -> BotSettingsDto:
        row = await self._get_or_create_singleton(BotSettings)
        row.proxy_url = proxy_url

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    def _to_shop_dto(self, row: Optional[ShopSettings]) -> ShopSettingsDto:
        if row is None:
            return ShopSettingsDto()
        return ShopSettingsDto.model_validate(row, from_attributes=True)

    async def get_shop_settings(self) -> ShopSettingsDto:
        row = await self.session.get(ShopSettings, _SINGLETON_ID)
        return self._to_shop_dto(row)

    async def update_shop_settings(self, data: UpdateShopSettingsDto) -> ShopSettingsDto:
        row = await self._get_or_create_singleton(ShopSettings)
        row.max_active_subscriptions = data.max_active_subscriptions
        row.device_single_reset_enabled = data.device_single_reset_enabled
        row.device_single_reset_cooldown_hours = data.device_single_reset_cooldown_hours
        row.device_all_reset_enabled = data.device_all_reset_enabled
        row.device_all_reset_cooldown_hours = data.device_all_reset_cooldown_hours
        row.link_reset_enabled = data.link_reset_enabled
        row.link_reset_cooldown_hours = data.link_reset_cooldown_hours

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_shop_dto(row)

    def _to_oauth_dto(self, row: Optional[OAuthSettings]) -> OAuthSettingsDto:
        if row is None:
            return OAuthSettingsDto()
        return OAuthSettingsDto.model_validate(row, from_attributes=True)

    async def get_oauth_settings(self) -> OAuthSettingsDto:
        row = await self.session.get(OAuthSettings, _SINGLETON_ID)
        return self._to_oauth_dto(row)

    async def update_oauth_settings(self, data: UpdateOAuthSettingsDto) -> OAuthSettingsDto:
        row = await self._get_or_create_singleton(OAuthSettings)

        apply_partial_update(row, data)

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_oauth_dto(row)

    def _to_appearance_dto(self, row: Optional[AppearanceSettings]) -> AppearanceSettingsDto:
        if row is None:
            return AppearanceSettingsDto()

        return AppearanceSettingsDto(
            id=row.id,
            brand_name=row.brand_name,
            primary_color=row.primary_color,
            shader_palette=row.shader_palette,
            shader_enabled=row.shader_enabled,
            has_logo=row.logo_extension is not None,
            has_favicon=row.favicon_extension is not None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_appearance_settings(self) -> AppearanceSettingsDto:
        row = await self.session.get(AppearanceSettings, _SINGLETON_ID)
        return self._to_appearance_dto(row)

    async def update_appearance_settings(
        self, data: UpdateAppearanceSettingsDto
    ) -> AppearanceSettingsDto:
        row = await self._get_or_create_singleton(AppearanceSettings)
        apply_partial_update(row, data)

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_appearance_dto(row)

    async def reset_appearance_settings(self) -> AppearanceSettingsDto:
        row = await self._get_or_create_singleton(AppearanceSettings)

        row.brand_name = None
        row.primary_color = None
        row.shader_palette = None
        row.shader_enabled = True

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_appearance_dto(row)

    async def get_appearance_image_meta(
        self, kind: AppearanceImageKind
    ) -> Optional[tuple[str, str]]:
        row = await self.session.get(AppearanceSettings, _SINGLETON_ID)
        if row is None:
            return None

        if kind == AppearanceImageKind.LOGO:
            if row.logo_extension is None or row.logo_content_type is None:
                return None
            return row.logo_extension, row.logo_content_type

        if row.favicon_extension is None or row.favicon_content_type is None:
            return None
        return row.favicon_extension, row.favicon_content_type

    async def set_appearance_image(
        self, kind: AppearanceImageKind, content_type: str, extension: str
    ) -> AppearanceSettingsDto:
        row = await self._get_or_create_singleton(AppearanceSettings)

        if kind == AppearanceImageKind.LOGO:
            row.logo_content_type = content_type
            row.logo_extension = extension
        else:
            row.favicon_content_type = content_type
            row.favicon_extension = extension

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_appearance_dto(row)

    async def clear_appearance_image(self, kind: AppearanceImageKind) -> AppearanceSettingsDto:
        row = await self._get_or_create_singleton(AppearanceSettings)

        if kind == AppearanceImageKind.LOGO:
            row.logo_content_type = None
            row.logo_extension = None
        else:
            row.favicon_content_type = None
            row.favicon_extension = None

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_appearance_dto(row)

    def _to_command_dto(self, row: BotCommand) -> BotCommandDto:
        return BotCommandDto.model_validate(row, from_attributes=True)

    async def list_bot_commands(self) -> list[BotCommandDto]:
        result = await self.session.execute(select(BotCommand).order_by(BotCommand.sort_order))
        return [self._to_command_dto(row) for row in result.scalars()]

    async def replace_bot_commands(self, commands: list[tuple[str, bool]]) -> list[BotCommandDto]:
        await self.session.execute(select(func.pg_advisory_xact_lock(_BOT_COMMANDS_LOCK_KEY)))

        await self.session.execute(delete(BotCommand))

        rows = [
            BotCommand(command=command, sort_order=index, enabled=enabled)
            for index, (command, enabled) in enumerate(commands)
        ]
        self.session.add_all(rows)

        await self.session.flush()
        result = await self.session.execute(select(BotCommand).order_by(BotCommand.sort_order))
        return [self._to_command_dto(row) for row in result.scalars()]
