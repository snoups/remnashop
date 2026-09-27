from typing import Final, Optional, TypeVar

from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.active_locale import ActiveLocale
from app.core.db.models.appearance_settings import AppearanceSettings
from app.core.db.models.bot_command import BotCommand
from app.core.db.models.bot_settings import BotSettings
from app.core.db.models.oauth_settings import OAuthSettings
from app.core.db.models.shop_settings import ShopSettings
from app.core.db.partial_update import apply_partial_update
from app.core.db.singleton import get_or_create_singleton
from app.core.enums import AppearanceImageKind, AppearanceResetScope, Locale
from app.core.exceptions import ConflictError
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
# Arbitrary fixed key for pg_advisory_xact_lock -- serializes concurrent
# replace_bot_commands calls so a delete+insert pair can't interleave with
# another one (plain DELETE FROM without WHERE re-evaluates its row set after
# a lock wait, so two concurrent replacements could otherwise both insert
# instead of the second cleanly replacing the first).
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

        return BotSettingsDto(
            id=row.id,
            token=SecretStr(row.token) if row.token is not None else None,
            secret_token=SecretStr(row.secret_token) if row.secret_token is not None else None,
            drop_pending_updates=row.drop_pending_updates,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_bot_settings(self) -> BotSettingsDto:
        row = await self.session.get(BotSettings, _SINGLETON_ID)
        return self._to_dto(row)

    async def update_bot_settings(self, data: UpdateBotSettingsDto) -> BotSettingsDto:
        # get-or-create on a fixed id=1, not a DB constraint like OWNER's
        # partial unique index -- a concurrent first-ever write can race here,
        # but id is still the primary key, so the loser gets an IntegrityError
        # rather than a duplicate row. Deliberately left low-stakes/unhardened
        # (see CLAUDE.md's Settings & Secrets section).
        row = await self._get_or_create_singleton(BotSettings)

        if data.token is not None:
            row.token = data.token
        if data.secret_token is not None:
            row.secret_token = data.secret_token
        if data.drop_pending_updates is not None:
            row.drop_pending_updates = data.drop_pending_updates

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    def _to_shop_dto(self, row: Optional[ShopSettings]) -> ShopSettingsDto:
        if row is None:
            return ShopSettingsDto()
        return ShopSettingsDto(
            id=row.id,
            max_active_subscriptions=row.max_active_subscriptions,
            device_single_reset_enabled=row.device_single_reset_enabled,
            device_single_reset_cooldown_hours=row.device_single_reset_cooldown_hours,
            device_all_reset_enabled=row.device_all_reset_enabled,
            device_all_reset_cooldown_hours=row.device_all_reset_cooldown_hours,
            link_reset_enabled=row.link_reset_enabled,
            link_reset_cooldown_hours=row.link_reset_cooldown_hours,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

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

        return OAuthSettingsDto(
            id=row.id,
            github_client_id=row.github_client_id,
            github_client_secret=(
                SecretStr(row.github_client_secret)
                if row.github_client_secret is not None
                else None
            ),
            github_enabled=row.github_enabled,
            telegram_client_id=row.telegram_client_id,
            telegram_client_secret=(
                SecretStr(row.telegram_client_secret)
                if row.telegram_client_secret is not None
                else None
            ),
            telegram_enabled=row.telegram_enabled,
            oidc_issuer_url=row.oidc_issuer_url,
            oidc_client_id=row.oidc_client_id,
            oidc_client_secret=(
                SecretStr(row.oidc_client_secret) if row.oidc_client_secret is not None else None
            ),
            oidc_display_name=row.oidc_display_name,
            oidc_enabled=row.oidc_enabled,
            password_login_enabled=row.password_login_enabled,
            passkey_enabled=row.passkey_enabled,
            passkey_rp_id=row.passkey_rp_id,
            passkey_origin=row.passkey_origin,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_oauth_settings(self) -> OAuthSettingsDto:
        row = await self.session.get(OAuthSettings, _SINGLETON_ID)
        return self._to_oauth_dto(row)

    async def update_oauth_settings(self, data: UpdateOAuthSettingsDto) -> OAuthSettingsDto:
        # Same deliberate low-stakes tradeoff as update_bot_settings() above.
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

        if data.brand_name is not None:
            row.brand_name = data.brand_name
        if data.primary_color is not None:
            row.primary_color = data.primary_color
        if data.shader_palette is not None:
            row.shader_palette = data.shader_palette
        if data.shader_enabled is not None:
            row.shader_enabled = data.shader_enabled

        await self.session.flush()
        await self.session.refresh(row)
        return self._to_appearance_dto(row)

    async def reset_appearance_settings(self, scope: AppearanceResetScope) -> AppearanceSettingsDto:
        row = await self._get_or_create_singleton(AppearanceSettings)

        if scope == AppearanceResetScope.BRANDING:
            row.brand_name = None
        else:
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
        return BotCommandDto(
            id=row.id,
            command=row.command,
            sort_order=row.sort_order,
            enabled=row.enabled,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

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

    async def list_active_locales(self) -> list[Locale]:
        result = await self.session.execute(select(ActiveLocale.locale))
        return list(result.scalars())

    async def add_active_locale(self, locale: Locale) -> None:
        self.session.add(ActiveLocale(locale=locale))
        try:
            await self.session.flush()
        except IntegrityError as error:
            raise ConflictError(f"Locale already active: {locale}") from error

    async def remove_active_locale(self, locale: Locale) -> None:
        await self.session.execute(delete(ActiveLocale).where(ActiveLocale.locale == locale))
