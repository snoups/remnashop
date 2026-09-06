import pytest
from redis.asyncio import Redis

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.modules.settings.dto import UpdateBotSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import UpdateBotSettingsUseCase
from app.modules.translations.repository import TranslationsRepository
from app.modules.translations.usecases import (
    ListTranslationsUseCase,
    ResetTranslationUseCase,
    UpdateTranslationUseCase,
)
from app.modules.translations.usecases.reset_translation import ResetTranslationInput
from app.modules.translations.usecases.update_translation import UpdateTranslationInput
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def _seed(
    settings_repository: SettingsRepository, translations_repository: TranslationsRepository
) -> None:
    await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Open the main menu")


async def test_owner_can_list_translations(
    settings_repository: SettingsRepository, translations_repository: TranslationsRepository
) -> None:
    await _seed(settings_repository, translations_repository)
    use_case = ListTranslationsUseCase(translations_repository)

    entries = await use_case(OWNER)

    assert [(e.locale, e.message_id, e.attribute_id, e.value) for e in entries] == [
        (Locale.EN, "command", "menu", "Open the main menu")
    ]


async def test_owner_can_update_translation_value(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translations_repository)
    use_case = UpdateTranslationUseCase(
        translations_repository, settings_repository, uow, config, redis
    )

    updated = await use_case(
        OWNER,
        UpdateTranslationInput(
            locale=Locale.EN, message_id="command", attribute_id="menu", value="New text"
        ),
    )

    assert updated.value == "New text"
    assert updated.default_value == "Open the main menu"


async def test_update_translation_rejects_invalid_fluent_syntax(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translations_repository)
    use_case = UpdateTranslationUseCase(
        translations_repository, settings_repository, uow, config, redis
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateTranslationInput(
                locale=Locale.EN, message_id="command", attribute_id="menu", value="{ unterminated"
            ),
        )

    entry = await translations_repository.get(Locale.EN, "command", "menu")
    assert entry is not None
    assert entry.value == "Open the main menu"


async def test_update_translation_rejects_placeables(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translations_repository)
    use_case = UpdateTranslationUseCase(
        translations_repository, settings_repository, uow, config, redis
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateTranslationInput(
                locale=Locale.EN, message_id="command", attribute_id="menu", value="Hi { $name }"
            ),
        )

    entry = await translations_repository.get(Locale.EN, "command", "menu")
    assert entry is not None
    assert entry.value == "Open the main menu"


async def test_update_translation_raises_not_found_for_unknown_key(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translations_repository)
    use_case = UpdateTranslationUseCase(
        translations_repository, settings_repository, uow, config, redis
    )

    with pytest.raises(NotFoundError):
        await use_case(
            OWNER,
            UpdateTranslationInput(
                locale=Locale.RU, message_id="command", attribute_id="menu", value="New text"
            ),
        )


async def test_reset_translation_raises_not_found_for_unknown_key(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translations_repository)
    use_case = ResetTranslationUseCase(
        translations_repository, settings_repository, uow, config, redis
    )

    with pytest.raises(NotFoundError):
        await use_case(
            OWNER,
            ResetTranslationInput(locale=Locale.RU, message_id="command", attribute_id="menu"),
        )


async def test_update_translation_repushes_to_telegram_when_bot_configured(
    monkeypatch: pytest.MonkeyPatch,
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
    redis: Redis,
) -> None:
    from aiogram import Bot  # noqa: PLC0415
    from aiogram.methods.set_my_commands import SetMyCommands  # noqa: PLC0415

    await _seed(settings_repository, translations_repository)
    await UpdateBotSettingsUseCase(settings_repository, uow)(
        OWNER, UpdateBotSettingsDto(token="123:abcdef", secret_token="webhook-secret")
    )

    pushed: list[SetMyCommands] = []

    async def _capturing_call(self: Bot, method: SetMyCommands, request_timeout=None):  # type: ignore[no-untyped-def]
        pushed.append(method)
        return True

    monkeypatch.setattr(Bot, "__call__", _capturing_call)

    use_case = UpdateTranslationUseCase(
        translations_repository, settings_repository, uow, config, redis
    )
    await use_case(
        OWNER,
        UpdateTranslationInput(
            locale=Locale.EN, message_id="command", attribute_id="menu", value="New text"
        ),
    )

    assert pushed
    assert pushed[0].commands[0].description == "New text"


async def test_owner_can_reset_translation_to_default(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translations_repository)
    update_use_case = UpdateTranslationUseCase(
        translations_repository, settings_repository, uow, config, redis
    )
    await update_use_case(
        OWNER,
        UpdateTranslationInput(
            locale=Locale.EN, message_id="command", attribute_id="menu", value="Changed"
        ),
    )
    reset_use_case = ResetTranslationUseCase(
        translations_repository, settings_repository, uow, config, redis
    )

    reset = await reset_use_case(
        OWNER, ResetTranslationInput(locale=Locale.EN, message_id="command", attribute_id="menu")
    )

    assert reset.value == "Open the main menu"


async def test_regular_user_cannot_update_translation(
    settings_repository: SettingsRepository,
    translations_repository: TranslationsRepository,
    uow: UnitOfWork,
    config: AppConfig,
    redis: Redis,
) -> None:
    await _seed(settings_repository, translations_repository)
    use_case = UpdateTranslationUseCase(
        translations_repository, settings_repository, uow, config, redis
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdateTranslationInput(
                locale=Locale.EN, message_id="command", attribute_id="menu", value="x"
            ),
        )
