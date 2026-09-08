from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
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


def _catalog_text_keys() -> set[str]:
    # Every text key a catalog-registered dialog window or button genuinely owns.
    # Custom windows aren't in the in-process catalog, hence the prefix check the
    # caller layers on top of this set.
    keys: set[str] = set()
    for window in catalog.all_windows():
        keys.update(window.text_keys)
        keys.update(button.text_key for button in window.buttons)
    return keys


class UpdateDialogTextUseCase(UseCase[UpdateDialogTextInput, TranslationEntryDto]):
    required_permission = Permission.DIALOGS_TEXT_UPDATE

    def __init__(
        self, translations_repository: TranslationsRepository, uow: UnitOfWork, redis: Redis
    ) -> None:
        self._translations_repository = translations_repository
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: UserDto, data: UpdateDialogTextInput) -> TranslationEntryDto:
        # Lazy import -- fluent_compiler lives under the telegram extra.
        from fluent_compiler.bundle import FluentBundle  # noqa: PLC0415

        full_key = data.message_id
        if data.attribute_id:
            full_key = f"{data.message_id}.{data.attribute_id}"
        if full_key not in _catalog_text_keys() and not full_key.startswith(
            catalog.CUSTOM_TEXT_KEY_PREFIX
        ):
            # This endpoint's relaxed placeable rule is dialogs-scoped -- it must
            # not become a back door for editing arbitrary translations rows
            # (bot commands, notifications) that the general editor guards more
            # strictly and repushes on change.
            raise ValidationError(f"'{full_key}' is not an editable dialog text key")

        if "\n" in data.value:
            raise ValidationError("Translation values cannot contain newlines")

        disallowed = find_disallowed_placeable(data.value, catalog.text_variable_keys())
        if disallowed is not None:
            raise ValidationError(disallowed)

        existing = await self._translations_repository.list_by_locale(data.locale)
        candidate = [
            entry
            for entry in existing
            if not (entry.message_id == data.message_id and entry.attribute_id == data.attribute_id)
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
