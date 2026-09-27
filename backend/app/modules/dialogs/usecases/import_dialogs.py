from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.enums import DialogWindowKind, Locale
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import (
    CreateCustomWindowDto,
    DialogExportDto,
    DialogWindowExportDto,
    UpdateDialogWindowDto,
)
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases._publish import publish_dialog_change
from app.modules.dialogs.usecases._window_texts import validate_stored_window_texts
from app.modules.dialogs.usecases.export_dialogs import EXPORT_VERSION, dialog_text_keys
from app.modules.dialogs.validation import validate_buttons
from app.modules.settings import SettingsRepository
from app.modules.translations import (
    TranslationsRepository,
    join_message_key,
    serialize_to_fluent,
)
from app.modules.users import UserDto


class ImportDialogsUseCase(UseCase[DialogExportDto, None]):
    """Replaces the whole dialog configuration with the imported one: seed
    windows are overwritten, custom windows are brought in line with the file,
    and custom windows missing from it are deleted."""

    required_permission = Permission.DIALOGS_IMPORT

    def __init__(
        self,
        dialog_repository: DialogRepository,
        translations_repository: TranslationsRepository,
        settings_repository: SettingsRepository,
        uow: UnitOfWork,
        redis: Redis,
    ) -> None:
        self._dialog_repository = dialog_repository
        self._translations_repository = translations_repository
        self._settings_repository = settings_repository
        self._uow = uow
        self._redis = redis

    async def _execute(self, actor: UserDto, data: DialogExportDto) -> None:
        if data.version != EXPORT_VERSION:
            raise ValidationError(
                f"Unsupported export version {data.version}, expected {EXPORT_VERSION}"
            )

        async with self._uow:
            existing = await self._dialog_repository.list_all()
            imported_keys = {window.key for window in data.windows}

            for current in existing:
                if current.kind == DialogWindowKind.CUSTOM and current.key not in imported_keys:
                    await self._dialog_repository.delete_custom_window(current.key)

            known_keys = {
                current.key
                for current in existing
                if current.kind != DialogWindowKind.CUSTOM or current.key in imported_keys
            }
            navigable = imported_keys | {window.key for window in catalog.all_windows()}
            for imported in data.windows:
                await self._apply_window(imported, known_keys, navigable)

            windows = await self._dialog_repository.list_all()
            await self._apply_texts(data, dialog_text_keys(windows))
            for window in windows:
                await validate_stored_window_texts(
                    window.key,
                    window.banner_name,
                    self._translations_repository,
                    self._settings_repository,
                )

        await publish_dialog_change(self._redis)

    async def _apply_window(
        self,
        window: DialogWindowExportDto,
        known_keys: set[str],
        navigable: set[str],
    ) -> None:
        if window.key not in known_keys:
            if window.kind == DialogWindowKind.SEED:
                # Seed windows come from the in-process catalog, not from a file:
                # one this build doesn't know about has no flow, no snapshot and
                # no state to render through.
                return
            await self._dialog_repository.create_custom_window(
                window.key,
                CreateCustomWindowDto(
                    banner_name=window.banner_name, name=window.name, position=window.position
                ),
            )

        seed_actions = (
            await self._dialog_repository.seed_action_keys(window.key)
            if window.kind == DialogWindowKind.SEED
            else set()
        )
        validate_buttons(
            window.buttons,
            window_key=window.key,
            window_kind=window.kind,
            navigable=navigable,
            seed_actions=seed_actions,
            system_text_keys=await self._dialog_repository.system_text_keys(window.key),
        )
        await self._dialog_repository.update_window(
            window.key,
            UpdateDialogWindowDto(
                banner_name=window.banner_name,
                banner_name_provided=True,
                # seed windows are always on, whatever an older export says
                is_enabled=True if window.kind == DialogWindowKind.SEED else window.is_enabled,
            ),
        )
        await self._dialog_repository.replace_buttons(window.key, window.buttons)

    async def _apply_texts(self, data: DialogExportDto, text_keys: set[str]) -> None:
        active = set(await self._settings_repository.list_active_locales())
        touched: set[Locale] = set()

        for text in data.texts:
            if text.locale not in active:
                continue
            if "." in text.message_id:
                raise ValidationError(
                    f"'{text.message_id}' is a message id plus an attribute -- "
                    "pass the attribute as attribute_id"
                )
            if join_message_key(text.message_id, text.attribute_id) not in text_keys:
                # Import must not become a back door into translations that have
                # nothing to do with dialogs, such as bot command descriptions.
                continue
            await self._translations_repository.seed_missing(
                text.locale, text.message_id, text.attribute_id, text.value
            )
            await self._translations_repository.update_value(
                text.locale, text.message_id, text.attribute_id, text.value
            )
            touched.add(text.locale)

        # Lazy import -- fluent_compiler lives under the telegram extra.
        from fluent_compiler.bundle import FluentBundle  # noqa: PLC0415

        for locale in touched:
            entries = await self._translations_repository.list_by_locale(locale)
            bundle = FluentBundle.from_string(  # type: ignore[no-untyped-call]
                locale.value, text=serialize_to_fluent(entries)
            )
            errors = bundle.check_messages()
            if errors:
                raise ValidationError(f"Invalid Fluent syntax in {locale.value}: {errors[0][1]}")
