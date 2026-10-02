from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import BotCommandsSync, BotSignals
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import TranslationEntryDto, UpdateTranslationDto
from app.modules.translations.repository import TranslationRepository
from app.modules.translations.serializer import (
    assert_fluent_compiles,
    contains_placeable,
    serialize_to_fluent,
)


class UpdateTranslationUseCase(UseCase[UpdateTranslationDto, TranslationEntryDto]):
    required_permission = Permission.TRANSLATIONS_UPDATE

    def __init__(
        self,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
        bot_commands: BotCommandsSync,
        bot_signals: BotSignals,
    ) -> None:
        self._translation_repository = translation_repository
        self._uow = uow
        self._bot_commands = bot_commands
        self._bot_signals = bot_signals

    async def _execute(self, actor: Actor, data: UpdateTranslationDto) -> TranslationEntryDto:
        async with self._uow:
            if "\n" in data.value:
                # Kept single-line even though serialize_to_fluent() now indents
                # continuations: this editor reaches every key, including the bot
                # command descriptions repushed below, which Telegram rejects
                # unless they are one line. Dialog window bodies get their
                # newlines through modules/dialogs' own text endpoint instead.
                raise ValidationError(
                    "Translation values cannot contain newlines",
                    code=ErrorCode.TRANSLATION_HAS_NEWLINES,
                )

            existing = await self._translation_repository.list_by_locale(data.locale)
            candidate = [
                entry
                for entry in existing
                if not (
                    entry.message_id == data.message_id and entry.attribute_id == data.attribute_id
                )
            ]
            candidate.append(
                TranslationEntryDto(
                    locale=data.locale,
                    message_id=data.message_id,
                    attribute_id=data.attribute_id,
                    value=data.value,
                    default_value=data.value,
                )
            )
            candidate_text = serialize_to_fluent(candidate)
            assert_fluent_compiles(data.locale, candidate_text)
            # Checked against just this one submitted value, not candidate_text
            # (the whole locale) -- scoping to the whole locale would reject an
            # edit to any OTHER key the moment one placeable-bearing value exists
            # anywhere in it (e.g. seeded bot-menu content), which isn't what
            # this restriction is meant to catch. contains_placeable needs a
            # full "id = value" line to parse a Pattern at all, hence the
            # throwaway id.
            if contains_placeable(f"placeholder-id = {data.value}"):
                raise ValidationError(
                    "Fluent placeables are not supported in translation values",
                    code=ErrorCode.TRANSLATION_HAS_PLACEABLES,
                )

        async with self._uow:
            updated = await self._translation_repository.update_value(
                data.locale, data.message_id, data.attribute_id, data.value
            )

        await self._bot_signals.translation_changed(
            data.locale, data.message_id, data.attribute_id, data.value
        )

        await self._bot_commands.push()
        return updated
