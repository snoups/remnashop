from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.ports import BotSignals, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.translations.dto import TranslationEntryDto, UpdateTranslationDto
from app.modules.translations.events import TranslationChangedEvent
from app.modules.translations.ports import BotCommandsSync
from app.modules.translations.repository import TranslationRepository
from app.modules.translations.serializer import (
    assert_fluent_compiles,
    assert_translation_value,
    assert_valid_bot_html,
    join_message_key,
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
        event_publisher: EventPublisher,
    ) -> None:
        self._translation_repository = translation_repository
        self._uow = uow
        self._bot_commands = bot_commands
        self._bot_signals = bot_signals
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateTranslationDto) -> TranslationEntryDto:
        assert_valid_bot_html(data.message_id, data.value)

        async with self._uow:
            current = await self._translation_repository.get_by_key(
                data.locale, data.message_id, data.attribute_id
            )
            assert_translation_value(data.message_id, data.value, current.default_value)
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

            updated = await self._translation_repository.update_value(
                data.locale, data.message_id, data.attribute_id, data.value
            )
            await self._event_publisher.publish(
                TranslationChangedEvent(
                    actor=actor,
                    action="update",
                    locale=data.locale,
                    key=join_message_key(data.message_id, data.attribute_id),
                )
            )

        await self._bot_signals.translation_changed(
            data.locale, data.message_id, data.attribute_id, data.value
        )

        await self._bot_commands.push()
        return updated
