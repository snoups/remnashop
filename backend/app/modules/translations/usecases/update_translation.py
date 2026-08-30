from dataclasses import dataclass

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.settings import SettingsRepository
from app.modules.translations.dto import TranslationEntryDto
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
    ) -> None:
        self._translations_repository = translations_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._config = config

    async def _execute(self, actor: UserDto, data: UpdateTranslationInput) -> TranslationEntryDto:
        # Lazy import -- fluent_compiler lives under the telegram extra.
        from fluent_compiler.bundle import FluentBundle  # noqa: PLC0415

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
        if contains_placeable(candidate_text):
            raise ValidationError("Fluent placeables are not supported in translation values")

        async with self._uow:
            updated = await self._translations_repository.update_value(
                data.locale, data.message_id, data.attribute_id, data.value
            )

        await repush_bot_commands_if_configured(
            self._settings_repository, self._translations_repository, self._config
        )
        return updated
