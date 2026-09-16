from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings import SettingsRepository
from app.modules.translations.dto import TranslationEntryDto
from app.modules.translations.publish import publish_translation_change
from app.modules.translations.repository import TranslationsRepository
from app.modules.translations.serializer import contains_placeable, serialize_to_fluent
from app.modules.translations.usecases._repush import repush_bot_commands_if_configured
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class UpdateTranslationInput:
    locale: Locale
    message_id: str
    attribute_id: str
    value: str


class UpdateTranslationUseCase(UseCase[UpdateTranslationInput, TranslationEntryDto]):
    required_permission = Permission.TRANSLATIONS_UPDATE

    def __init__(
        self,
        translations_repository: TranslationsRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        config: AppConfig,
        redis: Redis,
    ) -> None:
        self._translations_repository = translations_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._config = config
        self._redis = redis

    async def _execute(self, actor: UserDto, data: UpdateTranslationInput) -> TranslationEntryDto:
        # Lazy import -- fluent_compiler lives under the telegram extra.
        async with self._uow:
            from fluent_compiler.bundle import FluentBundle  # noqa: PLC0415

            if "\n" in data.value:
                # A newline lets the value break out of its own line when
                # serialize_to_fluent() writes it back out, injecting a second
                # top-level Fluent message into the locale text.
                raise ValidationError("Translation values cannot contain newlines")

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
            # Checked against just this one submitted value, not candidate_text
            # (the whole locale) -- scoping to the whole locale would reject an
            # edit to any OTHER key the moment one placeable-bearing value exists
            # anywhere in it (e.g. seeded bot-menu content), which isn't what
            # this restriction is meant to catch. contains_placeable needs a
            # full "id = value" line to parse a Pattern at all, hence the
            # throwaway id.
            if contains_placeable(f"placeholder-id = {data.value}"):
                raise ValidationError("Fluent placeables are not supported in translation values")

        async with self._uow:
            updated = await self._translations_repository.update_value(
                data.locale, data.message_id, data.attribute_id, data.value
            )

        await publish_translation_change(
            self._redis, data.locale, data.message_id, data.value, attribute_id=data.attribute_id
        )

        await repush_bot_commands_if_configured(
            self._settings_repository, self._translations_repository, self._config, self._uow
        )
        return updated
