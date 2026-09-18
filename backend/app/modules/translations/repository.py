from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.bot_translation import BotTranslation
from app.core.enums import Locale
from app.core.exceptions import NotFoundError
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.serializer import serialize_to_fluent


class TranslationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _to_dto(self, row: BotTranslation) -> TranslationEntryDto:
        return TranslationEntryDto(
            id=row.id,
            locale=row.locale,
            message_id=row.message_id,
            attribute_id=row.attribute_id,
            value=row.value,
            default_value=row.default_value,
            created_at=row.created_at,
            updated_at=row.updated_at,
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
        # Deliberately only removes a row nobody has typed anything into: an
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
                f"Translation {message_id}.{attribute_id} not found for locale {locale.value}"
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
                f"Translation {message_id}.{attribute_id} not found for locale {locale.value}"
            )
        row.value = row.default_value
        await self.session.flush()
        await self.session.refresh(row)
        return self._to_dto(row)

    async def copy_locale_from(self, source: Locale, target: Locale) -> None:
        entries = await self.list_by_locale(source)
        rows = [
            BotTranslation(
                locale=target,
                message_id=entry.message_id,
                attribute_id=entry.attribute_id,
                value=entry.value,
                default_value=entry.value,
            )
            for entry in entries
        ]
        self.session.add_all(rows)
        await self.session.flush()

    async def delete_locale(self, locale: Locale) -> None:
        await self.session.execute(delete(BotTranslation).where(BotTranslation.locale == locale))
