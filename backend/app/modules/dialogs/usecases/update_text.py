from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.validation import validate_window_text
from app.modules.translations import (
    TranslationEntryDto,
    TranslationsRepository,
    find_disallowed_placeable,
    publish_translation_change,
    serialize_to_fluent,
)
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class UpdateDialogTextInput:
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


class UpdateDialogTextUseCase(UseCase[UpdateDialogTextInput, TranslationEntryDto]):
    required_permission = Permission.DIALOGS_TEXT_UPDATE

    def __init__(
        self,
        translations_repository: TranslationsRepository,
        dialog_repository: DialogRepository,
        uow: UnitOfWork,
        redis: Redis,
    ) -> None:
        self._translations_repository = translations_repository
        self._dialog_repository = dialog_repository
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: UserDto, data: UpdateDialogTextInput) -> TranslationEntryDto:
        # Lazy import -- fluent_compiler lives under the telegram extra.
        async with self._uow:
            from fluent_compiler.bundle import FluentBundle  # noqa: PLC0415

            if "." in data.message_id:
                # An attribute belongs in attribute_id; taking it here too would
                # write a second row that shadows the real one.
                raise ValidationError(
                    f"'{data.message_id}' is a message id plus an attribute -- "
                    "pass the attribute as attribute_id"
                )

            full_key = data.message_id
            if data.attribute_id:
                full_key = f"{data.message_id}.{data.attribute_id}"
            if not catalog.is_editable_text_key(full_key):
                # This endpoint's relaxed placeable rule is dialogs-scoped -- it must
                # not become a back door for editing arbitrary translations rows
                # (bot commands, notifications) that the general editor guards more
                # strictly and repushes on change.
                raise ValidationError(f"'{full_key}' is not an editable dialog text key")

            if not data.value.strip() and await self._dialog_repository.is_button_text_key(
                full_key
            ):
                # Telegram rejects the whole keyboard over one button with no text.
                raise ValidationError("A button label cannot be empty")

            window_key = catalog.window_key_for_text_key(full_key)
            window = await self._dialog_repository.get_by_key(window_key) if window_key else None
            if window is not None:
                validate_window_text(
                    data.value, has_banner=window.banner_name is not None, locale=data.locale
                )

            # Newlines are fine here, unlike in the general translations editor:
            # serialize_to_fluent() indents continuation lines, and a window's
            # body is the one piece of bot text that genuinely wants paragraphs.
            disallowed = find_disallowed_placeable(data.value, catalog.text_variable_keys())
            if disallowed is not None:
                raise ValidationError(disallowed)

            existing = await self._translations_repository.list_by_locale(data.locale)
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
            bundle = FluentBundle.from_string(  # type: ignore[no-untyped-call]
                data.locale.value, text=candidate_text
            )
            errors = bundle.check_messages()
            if errors:
                raise ValidationError(f"Invalid Fluent syntax: {errors[0][1]}")

        async with self._uow:
            updated = await self._translations_repository.update_value(
                data.locale, data.message_id, data.attribute_id, data.value
            )

        await publish_translation_change(
            self._redis, data.locale, data.message_id, data.value, attribute_id=data.attribute_id
        )
        return updated
