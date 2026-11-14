from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import BotSignals, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import (
    EXPORT_VERSION,
    TranslationsImportDto,
    TranslationsImportResultDto,
    TranslationTextExportDto,
)
from app.modules.translations.events import TranslationChangedEvent
from app.modules.translations.ports import BotCommandsSync
from app.modules.translations.repository import TranslationRepository
from app.modules.translations.serializer import (
    assert_fluent_compiles,
    assert_translation_value,
    assert_valid_bot_html,
    serialize_to_fluent,
)


class ImportTranslationsUseCase(UseCase[TranslationsImportDto, TranslationsImportResultDto]):
    required_permission = Permission.TRANSLATIONS_IMPORT

    def __init__(
        self,
        translation_repository: TranslationRepository,
        uow: UnitOfWork,
        bot_commands: BotCommandsSync,
        bot_signals: BotSignals,
        event_publisher: EventPublisher,
    ) -> None:
        self._translation_repository = translation_repository
        self._uow = uow
        self._bot_commands = bot_commands
        self._bot_signals = bot_signals
        self._event_publisher = event_publisher

    async def _execute(
        self, actor: Actor, data: TranslationsImportDto
    ) -> TranslationsImportResultDto:
        if data.version != EXPORT_VERSION:
            raise ValidationError(
                f"Unsupported export version {data.version}, expected {EXPORT_VERSION}",
                code=ErrorCode.TRANSLATION_EXPORT_VERSION_UNSUPPORTED,
            )

        applied: list[TranslationTextExportDto] = []
        skipped = 0
        async with self._uow:
            defaults = {
                (entry.locale, entry.message_id, entry.attribute_id): entry.default_value
                for locale in await self._translation_repository.list_active_locales()
                for entry in await self._translation_repository.list_by_locale(locale)
            }
            for text in data.texts:
                # a string this install doesn't have (a disabled locale, a key
                # from an older catalog) is skipped; nothing would ever read it
                default_value = defaults.get((text.locale, text.message_id, text.attribute_id))
                if default_value is None:
                    skipped += 1
                    continue
                assert_translation_value(text.message_id, text.value, default_value)
                assert_valid_bot_html(text.message_id, text.value)
                await self._translation_repository.update_value(
                    text.locale, text.message_id, text.attribute_id, text.value
                )
                applied.append(text)
            # raising here rolls the whole import back, as a hand edit would be refused
            for locale in {text.locale for text in applied}:
                entries = await self._translation_repository.list_by_locale(locale)
                assert_fluent_compiles(locale, serialize_to_fluent(entries))
            await self._event_publisher.publish(
                TranslationChangedEvent(actor=actor, action="import")
            )

        # one full reload instead of a signal per key
        await self._bot_signals.dialogs_changed()

        await self._bot_commands.push()
        return TranslationsImportResultDto(applied=len(applied), skipped=skipped)
