from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.errors import constraint_name
from app.core.db.models.active_locale import ActiveLocale
from app.core.db.models.bot_translation import BotTranslation
from app.core.enums import Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.translations.dto import ActiveLocalesDto, TranslationEntryDto
from app.modules.translations.serializer import serialize_to_fluent


class TranslationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: BotTranslation) -> TranslationEntryDto:
        return TranslationEntryDto.model_validate(row, from_attributes=True)

    async def list_active_locales(self) -> list[Locale]:
        result = await self.session.execute(select(ActiveLocale.locale))
        return list(result.scalars())

    async def lock_active_locales(self) -> None:
        # set-default and remove both read then write this set; without the lock they
        # can interleave and leave no row flagged as the default
        await self.session.execute(select(ActiveLocale.id).with_for_update())

    async def add_active_locale(self, locale: Locale) -> None:
        self.session.add(ActiveLocale(locale=locale))
        try:
            await self.session.flush()
        except IntegrityError as error:
            if constraint_name(error) != "ux_active_locales_locale":
                raise
            raise ConflictError(
                f"Locale already active: {locale}", code=ErrorCode.LOCALE_ALREADY_ACTIVE
            ) from error

    async def remove_active_locale(self, locale: Locale) -> None:
        await self.session.execute(delete(ActiveLocale).where(ActiveLocale.locale == locale))

    async def get_locales(self) -> ActiveLocalesDto:
        return ActiveLocalesDto(
            active=await self.list_active_locales(), default=await self.get_default_locale()
        )

    async def find_default_locale(self) -> Optional[Locale]:
        result = await self.session.execute(
            select(ActiveLocale.locale).where(ActiveLocale.is_default)
        )
        return result.scalar_one_or_none()

    async def get_default_locale(self) -> Locale:
        # nothing flagged until ensure_translations_seeded() has run
        return await self.find_default_locale() or Locale.EN

    async def set_default_locale(self, locale: Locale) -> None:
        # cleared first: the partial unique index allows one flagged row per statement
        await self.session.execute(
            update(ActiveLocale).where(ActiveLocale.is_default).values(is_default=False)
        )
        await self.session.execute(
            update(ActiveLocale).where(ActiveLocale.locale == locale).values(is_default=True)
        )

    async def list_all(self) -> list[TranslationEntryDto]:
        result = await self.session.execute(
            select(BotTranslation).order_by(
                BotTranslation.message_id, BotTranslation.attribute_id, BotTranslation.locale
            )
        )
        return [self._to_dto(row) for row in result.scalars()]

    async def list_by_locale(self, locale: Locale) -> list[TranslationEntryDto]:
        result = await self.session.execute(
            select(BotTranslation).where(BotTranslation.locale == locale)
        )
        return [self._to_dto(row) for row in result.scalars()]

    async def get_fluent_text_by_locale(self, locales: list[Locale]) -> dict[Locale, str]:
        if not locales:
            return {}

        result = await self.session.execute(
            select(BotTranslation).where(BotTranslation.locale.in_(locales))
        )
        entries_by_locale: dict[Locale, list[TranslationEntryDto]] = {
            locale: [] for locale in locales
        }
        for row in result.scalars():
            entries_by_locale[row.locale].append(self._to_dto(row))

        return {
            locale: serialize_to_fluent(entries) for locale, entries in entries_by_locale.items()
        }

    async def get(
        self, locale: Locale, message_id: str, attribute_id: str
    ) -> Optional[TranslationEntryDto]:
        result = await self.session.execute(
            select(BotTranslation).where(
                BotTranslation.locale == locale,
                BotTranslation.message_id == message_id,
                BotTranslation.attribute_id == attribute_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_dto(row) if row is not None else None

    async def seed_missing(
        self, locale: Locale, message_id: str, attribute_id: str, value: str
    ) -> None:
        stmt = (
            pg_insert(BotTranslation)
            .values(
                locale=locale,
                message_id=message_id,
                attribute_id=attribute_id,
                value=value,
                default_value=value,
            )
            .on_conflict_do_nothing(index_elements=["locale", "message_id", "attribute_id"])
        )
        await self.session.execute(stmt)

    async def delete_blank(self, locale: Locale, message_id: str, attribute_id: str) -> None:
        # Only a row nobody has typed anything into goes: an
        # edited value is somebody's work, even if the row shouldn't exist.
        await self.session.execute(
            delete(BotTranslation).where(
                BotTranslation.locale == locale,
                BotTranslation.message_id == message_id,
                BotTranslation.attribute_id == attribute_id,
                BotTranslation.value == "",
            )
        )

    async def update_value(
        self, locale: Locale, message_id: str, attribute_id: str, value: str
    ) -> TranslationEntryDto:
        result = await self.session.execute(
            select(BotTranslation).where(
                BotTranslation.locale == locale,
                BotTranslation.message_id == message_id,
                BotTranslation.attribute_id == attribute_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError(
                f"Translation {message_id}.{attribute_id} not found for locale {locale.value}",
                code=ErrorCode.TRANSLATION_NOT_FOUND,
            )
        row.value = value
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def reset_value(
        self, locale: Locale, message_id: str, attribute_id: str
    ) -> TranslationEntryDto:
        result = await self.session.execute(
            select(BotTranslation).where(
                BotTranslation.locale == locale,
                BotTranslation.message_id == message_id,
                BotTranslation.attribute_id == attribute_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError(
                f"Translation {message_id}.{attribute_id} not found for locale {locale.value}",
                code=ErrorCode.TRANSLATION_NOT_FOUND,
            )
        row.value = row.default_value
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def reset_locale(self, locale: Locale) -> None:
        await self.session.execute(
            update(BotTranslation)
            .where(BotTranslation.locale == locale)
            .values(value=BotTranslation.default_value)
        )

    async def copy_locale_from(self, source: Locale, target: Locale) -> None:
        entries = await self.list_by_locale(source)
        if not entries:
            return

        # Deactivating a locale keeps its rows, so reactivating it must not
        # overwrite the translations somebody already wrote.
        stmt = pg_insert(BotTranslation).on_conflict_do_nothing(
            index_elements=["locale", "message_id", "attribute_id"]
        )
        await self.session.execute(
            stmt,
            [
                {
                    "locale": target,
                    "message_id": entry.message_id,
                    "attribute_id": entry.attribute_id,
                    "value": entry.value,
                    "default_value": entry.value,
                }
                for entry in entries
            ],
        )
