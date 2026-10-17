from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import BotSignals, EventPublisher
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import UpdateDialogTextDto
from app.modules.dialogs.events import DialogChangedEvent
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.validation import validate_window_text
from app.modules.translations import (
    TranslationEntryDto,
    TranslationRepository,
    assert_fluent_compiles,
    find_disallowed_placeable,
    serialize_to_fluent,
)


class UpdateDialogTextUseCase(UseCase[UpdateDialogTextDto, TranslationEntryDto]):
    required_permission = Permission.DIALOGS_TEXT_UPDATE

    def __init__(
        self,
        translation_repository: TranslationRepository,
        dialog_repository: DialogRepository,
        uow: UnitOfWork,
        bot_signals: BotSignals,
        event_publisher: EventPublisher,
    ) -> None:
        self._translation_repository = translation_repository
        self._dialog_repository = dialog_repository
        self._uow = uow
        self._bot_signals = bot_signals
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: UpdateDialogTextDto) -> TranslationEntryDto:
        async with self._uow:
            if "." in data.message_id:
                # An attribute belongs in attribute_id; taking it here too would
                # write a second row that shadows the real one.
                raise ValidationError(
                    f"'{data.message_id}' is a message id plus an attribute -- "
                    "pass the attribute as attribute_id",
                    code=ErrorCode.DIALOG_TEXT_KEY_HAS_ATTRIBUTE,
                )

            full_key = data.message_id
            if data.attribute_id:
                full_key = f"{data.message_id}.{data.attribute_id}"
            if not catalog.is_editable_text_key(full_key):
                # the relaxed placeable rule is for dialog text only; bot commands
                # and notifications go through the stricter general editor
                raise ValidationError(
                    f"'{full_key}' is not an editable dialog text key",
                    code=ErrorCode.DIALOG_TEXT_KEY_NOT_EDITABLE,
                )

            if not data.value.strip() and await self._dialog_repository.is_button_text_key(
                full_key
            ):
                # Telegram rejects the whole keyboard over one button with no text.
                raise ValidationError(
                    "A button label cannot be empty", code=ErrorCode.DIALOG_BUTTON_LABEL_EMPTY
                )

            window_key = catalog.window_key_for_text_key(full_key)
            window = await self._dialog_repository.get_by_key(window_key) if window_key else None
            if window is not None:
                validate_window_text(
                    data.value, has_banner=window.banner_name is not None, locale=data.locale
                )

            # Newlines are fine here, unlike in the general translations editor:
            # serialize_to_fluent() indents continuation lines, and a window's
            # body is the one piece of bot text that wants paragraphs.
            allowed_variables = catalog.text_variable_keys()
            if window_key and catalog.has_window(window_key):
                allowed_variables |= set(catalog.get_window(window_key).text_variables)
            disallowed = find_disallowed_placeable(data.value, allowed_variables)
            if disallowed is not None:
                raise ValidationError(disallowed, code=ErrorCode.DIALOG_TEXT_VARIABLE_NOT_ALLOWED)

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

            if catalog.is_icon_text_key(full_key):
                # An icon row exists only once something sets it: the assets seed
                # a few glyphs and no premium ids. Empty default, so a reset
                # takes the icon off.
                await self._translation_repository.seed_missing(
                    data.locale, data.message_id, data.attribute_id, ""
                )
            updated = await self._translation_repository.update_value(
                data.locale, data.message_id, data.attribute_id, data.value
            )
            await self._event_publisher.publish(
                DialogChangedEvent(actor=actor, action="text", window_key=window_key)
            )

        await self._bot_signals.translation_changed(
            data.locale, data.message_id, data.attribute_id, data.value
        )
        return updated
