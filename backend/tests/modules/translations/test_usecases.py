import pytest
from redis.asyncio import Redis

from app.core.bot_signals import RedisBotSignals
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.modules.settings.dto import UpdateBotSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import UpdateBotSettingsUseCase
from app.modules.translations.dto import (
    EXPORT_VERSION,
    ResetTranslationDto,
    TranslationsImportDto,
    TranslationTextExportDto,
    UpdateTranslationDto,
)
from app.modules.translations.repository import TranslationRepository
from app.modules.translations.usecases import (
    ExportTranslationsUseCase,
    ImportTranslationsUseCase,
    ListTranslationsUseCase,
    ResetAllTranslationsUseCase,
    ResetTranslationUseCase,
    UpdateTranslationUseCase,
)
from app.modules.users.dto import UserDto
from tests.fakes.events import RecordingEventPublisher
from tests.fakes.telegram_bot import FakeBotSession, use_fake_bot
from tests.modules.settings.factories import make_bot_commands_sync

OWNER = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def _seed(
    settings_repository: SettingsRepository, translation_repository: TranslationRepository
) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")


async def test_owner_can_list_translations(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await _seed(settings_repository, translation_repository)
    use_case = ListTranslationsUseCase(translation_repository, uow)

    entries = await use_case(OWNER)

    assert [(e.locale, e.message_id, e.attribute_id, e.value) for e in entries] == [
        (Locale.EN, "command", "menu", "Open the main menu")
    ]


async def test_owner_can_update_translation_value(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translation_repository)
    use_case = UpdateTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    updated = await use_case(
        OWNER,
        UpdateTranslationDto(
            locale=Locale.EN, message_id="command", attribute_id="menu", value="New text"
        ),
    )

    assert updated.value == "New text"
    assert updated.default_value == "Open the main menu"


async def test_update_translation_rejects_invalid_fluent_syntax(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    async with uow:
        await _seed(settings_repository, translation_repository)
    use_case = UpdateTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateTranslationDto(
                locale=Locale.EN, message_id="command", attribute_id="menu", value="{ unterminated"
            ),
        )

    entry = await translation_repository.get(Locale.EN, "command", "menu")
    assert entry is not None
    assert entry.value == "Open the main menu"


async def test_update_translation_rejects_placeables(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    async with uow:
        await _seed(settings_repository, translation_repository)
    use_case = UpdateTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateTranslationDto(
                locale=Locale.EN, message_id="command", attribute_id="menu", value="Hi { $name }"
            ),
        )

    entry = await translation_repository.get(Locale.EN, "command", "menu")
    assert entry is not None
    assert entry.value == "Open the main menu"


async def test_update_translation_raises_not_found_for_unknown_key(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translation_repository)
    use_case = UpdateTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    with pytest.raises(NotFoundError):
        await use_case(
            OWNER,
            UpdateTranslationDto(
                locale=Locale.RU, message_id="command", attribute_id="menu", value="New text"
            ),
        )


async def test_reset_translation_raises_not_found_for_unknown_key(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translation_repository)
    use_case = ResetTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    with pytest.raises(NotFoundError):
        await use_case(
            OWNER,
            ResetTranslationDto(locale=Locale.RU, message_id="command", attribute_id="menu"),
        )


async def test_update_translation_repushes_to_telegram_when_bot_configured(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translation_repository)
    # the description the registry actually points at
    await translation_repository.seed_missing(Locale.EN, "command", "start", "Open the main menu")
    await translation_repository.seed_missing(Locale.EN, "command", "paysupport", "Refunds")
    await translation_repository.seed_missing(Locale.EN, "command", "terms", "Terms")
    await UpdateBotSettingsUseCase(settings_repository, uow, RecordingEventPublisher())(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    session = use_fake_bot(
        monkeypatch, FakeBotSession({"SetMyCommands": True, "DeleteMyCommands": True})
    )

    use_case = UpdateTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )
    await use_case(
        OWNER,
        UpdateTranslationDto(
            locale=Locale.EN, message_id="command", attribute_id="start", value="New text"
        ),
    )

    pushed = session.called("SetMyCommands")
    assert pushed
    assert pushed[0].commands[0].description == "New text"


async def test_owner_can_reset_translation_to_default(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translation_repository)
    update_use_case = UpdateTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )
    await update_use_case(
        OWNER,
        UpdateTranslationDto(
            locale=Locale.EN, message_id="command", attribute_id="menu", value="Changed"
        ),
    )
    reset_use_case = ResetTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    reset = await reset_use_case(
        OWNER, ResetTranslationDto(locale=Locale.EN, message_id="command", attribute_id="menu")
    )

    assert reset.value == "Open the main menu"


async def test_regular_user_cannot_update_translation(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translation_repository)
    use_case = UpdateTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdateTranslationDto(
                locale=Locale.EN, message_id="command", attribute_id="menu", value="x"
            ),
        )


async def test_export_returns_every_active_locale_string(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    await _seed(settings_repository, translation_repository)

    export = await ExportTranslationsUseCase(translation_repository, uow)(OWNER)

    assert export.version == EXPORT_VERSION
    assert [(text.message_id, text.attribute_id, text.value) for text in export.texts] == [
        ("command", "menu", "Open the main menu")
    ]


async def test_import_applies_known_keys_and_skips_the_rest(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translation_repository)
    use_case = ImportTranslationsUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    result = await use_case(
        OWNER,
        TranslationsImportDto(
            version=EXPORT_VERSION,
            texts=[
                TranslationTextExportDto(
                    locale=Locale.EN, message_id="command", attribute_id="menu", value="Imported"
                ),
                # Unknown key and inactive locale: both land nowhere, so both
                # count as skipped instead of creating rows nothing reads.
                TranslationTextExportDto(
                    locale=Locale.EN, message_id="command", attribute_id="gone", value="Ghost"
                ),
                TranslationTextExportDto(
                    locale=Locale.RU, message_id="command", attribute_id="menu", value="Меню"
                ),
            ],
        ),
    )

    assert (result.applied, result.skipped) == (1, 2)
    entry = await translation_repository.get(Locale.EN, "command", "menu")
    assert entry is not None
    assert entry.value == "Imported"


async def test_import_rejects_a_foreign_export_version(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    use_case = ImportTranslationsUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError):
        await use_case(OWNER, TranslationsImportDto(version=EXPORT_VERSION + 1, texts=[]))


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("two\nlines", ErrorCode.TRANSLATION_HAS_NEWLINES),
        ("{ $name }", ErrorCode.TRANSLATION_HAS_PLACEABLES),
        ("broken }", ErrorCode.FLUENT_SYNTAX_INVALID),
    ],
)
async def test_import_refuses_what_a_hand_edit_would(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
    value: str,
    code: ErrorCode,
) -> None:
    await _seed(settings_repository, translation_repository)
    use_case = ImportTranslationsUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )
    texts = [
        TranslationTextExportDto(
            locale=Locale.EN, message_id="command", attribute_id="menu", value=value
        )
    ]

    with pytest.raises(ValidationError) as error:
        await use_case(OWNER, TranslationsImportDto(version=EXPORT_VERSION, texts=texts))

    assert error.value.code is code


async def test_reset_all_restores_every_edited_string(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translation_repository)
    await UpdateTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )(
        OWNER,
        UpdateTranslationDto(
            locale=Locale.EN, message_id="command", attribute_id="menu", value="Changed"
        ),
    )

    await ResetAllTranslationsUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )(OWNER)

    entry = await translation_repository.get(Locale.EN, "command", "menu")
    assert entry is not None
    assert entry.value == "Open the main menu"


async def test_regular_user_cannot_export_translations(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
) -> None:
    use_case = ExportTranslationsUseCase(translation_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER)


async def test_update_translation_rejects_invalid_html_in_a_window_text(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translation_repository)
    await translation_repository.seed_missing(Locale.EN, "msg-x", "", "Fine")
    use_case = UpdateTranslationUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError) as exc:
        await use_case(
            OWNER,
            UpdateTranslationDto(
                locale=Locale.EN, message_id="msg-x", attribute_id="", value="<b>x"
            ),
        )

    assert exc.value.code == ErrorCode.TRANSLATION_HTML_INVALID
    entry = await translation_repository.get(Locale.EN, "msg-x", "")
    assert entry is not None
    assert entry.value == "Fine"


async def test_import_rejects_the_whole_file_on_invalid_html(
    settings_repository: SettingsRepository,
    translation_repository: TranslationRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    async with uow:
        await _seed(settings_repository, translation_repository)
        await translation_repository.seed_missing(Locale.EN, "msg-x", "", "Fine")
    use_case = ImportTranslationsUseCase(
        translation_repository,
        uow,
        make_bot_commands_sync(settings_repository.session, uow),
        RedisBotSignals(redis),
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError) as exc:
        await use_case(
            OWNER,
            TranslationsImportDto(
                version=EXPORT_VERSION,
                texts=[
                    TranslationTextExportDto(
                        locale=Locale.EN, message_id="command", attribute_id="menu", value="Ok"
                    ),
                    TranslationTextExportDto(
                        locale=Locale.EN, message_id="msg-x", attribute_id="", value="<b>x"
                    ),
                ],
            ),
        )

    assert exc.value.code == ErrorCode.TRANSLATION_HTML_INVALID
    entry = await translation_repository.get(Locale.EN, "msg-x", "")
    assert entry is not None
    assert entry.value == "Fine"
