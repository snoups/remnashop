from pathlib import Path

import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.modules.banners.dto import BannerKeyDto, UploadBannerFileDto
from app.modules.banners.repository import BannerRepository
from app.modules.banners.usecases import (
    DeleteBannerUseCase,
    GetBannerImageUseCase,
    UploadBannerUseCase,
)
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import UserDto
from tests.fakes.events import RecordingEventPublisher

OWNER = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)

# Real JPEG/PNG magic bytes, so uploads exercise the actual magic-byte check
# instead of accidentally short-circuiting on it.
FAKE_JPEG: bytes = b"\xff\xd8\xff" + b"fake-jpg-body"
FAKE_PNG: bytes = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"


def _config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


async def _seed_locales(translation_repository: TranslationRepository) -> None:
    await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.add_active_locale(Locale.RU)


async def test_owner_can_upload_banner(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    use_case = UploadBannerUseCase(
        banner_repository,
        translation_repository,
        _config(config, tmp_path),
        uow,
        RecordingEventPublisher(),
    )

    banner = await use_case(
        OWNER,
        UploadBannerFileDto(
            name="menu", locale=Locale.RU, content_type="image/jpeg", data=FAKE_JPEG
        ),
    )

    assert banner.name == "menu"
    assert banner.extension == "jpg"
    assert banner.size_bytes == len(FAKE_JPEG)
    assert (tmp_path / "banners" / "menu_ru.jpg").read_bytes() == FAKE_JPEG


async def test_regular_user_cannot_upload_banner(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    use_case = UploadBannerUseCase(
        banner_repository,
        translation_repository,
        _config(config, tmp_path),
        uow,
        RecordingEventPublisher(),
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UploadBannerFileDto(
                name="menu", locale=Locale.RU, content_type="image/jpeg", data=b"x"
            ),
        )


async def test_upload_rejects_unsupported_content_type(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    use_case = UploadBannerUseCase(
        banner_repository,
        translation_repository,
        _config(config, tmp_path),
        uow,
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadBannerFileDto(
                name="menu", locale=Locale.RU, content_type="application/pdf", data=b"x"
            ),
        )


async def test_upload_rejects_locale_not_in_config(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    use_case = UploadBannerUseCase(
        banner_repository,
        translation_repository,
        _config(config, tmp_path),
        uow,
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadBannerFileDto(
                name="menu", locale=Locale.DE, content_type="image/jpeg", data=FAKE_JPEG
            ),
        )


async def test_upload_rejects_oversized_file(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    use_case = UploadBannerUseCase(
        banner_repository,
        translation_repository,
        _config(config, tmp_path),
        uow,
        RecordingEventPublisher(),
    )
    oversized = FAKE_JPEG + b"x" * (5 * 1024 * 1024 + 1)

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadBannerFileDto(
                name="menu", locale=Locale.RU, content_type="image/jpeg", data=oversized
            ),
        )


async def test_owner_can_delete_banner(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    cfg = _config(config, tmp_path)
    upload_use_case = UploadBannerUseCase(
        banner_repository, translation_repository, cfg, uow, RecordingEventPublisher()
    )
    delete_use_case = DeleteBannerUseCase(banner_repository, cfg, uow, RecordingEventPublisher())

    await upload_use_case(
        OWNER,
        UploadBannerFileDto(
            name="menu", locale=Locale.RU, content_type="image/jpeg", data=FAKE_JPEG
        ),
    )
    await delete_use_case(OWNER, BannerKeyDto(name="menu", locale=Locale.RU))

    assert await banner_repository.get("menu", Locale.RU) is None
    assert not (tmp_path / "banners" / "menu_ru.jpg").exists()


async def test_delete_missing_banner_raises_not_found(
    banner_repository: BannerRepository, config: AppConfig, uow: UnitOfWork, tmp_path: Path
) -> None:
    delete_use_case = DeleteBannerUseCase(
        banner_repository, _config(config, tmp_path), uow, RecordingEventPublisher()
    )

    with pytest.raises(NotFoundError):
        await delete_use_case(OWNER, BannerKeyDto(name="menu", locale=Locale.RU))


async def test_get_banner_image_returns_bytes_and_content_type(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    cfg = _config(config, tmp_path)
    upload_use_case = UploadBannerUseCase(
        banner_repository, translation_repository, cfg, uow, RecordingEventPublisher()
    )
    get_use_case = GetBannerImageUseCase(banner_repository, cfg, uow)

    await upload_use_case(
        OWNER,
        UploadBannerFileDto(
            name="menu", locale=Locale.RU, content_type="image/jpeg", data=FAKE_JPEG
        ),
    )

    result = await get_use_case(OWNER, BannerKeyDto(name="menu", locale=Locale.RU))
    data, content_type = result.data, result.content_type
    assert data == FAKE_JPEG
    assert content_type == "image/jpeg"


async def test_get_banner_image_missing_raises_not_found(
    banner_repository: BannerRepository,
    config: AppConfig,
    tmp_path: Path,
    uow: UnitOfWork,
) -> None:
    use_case = GetBannerImageUseCase(banner_repository, _config(config, tmp_path), uow)

    with pytest.raises(NotFoundError):
        await use_case(OWNER, BannerKeyDto(name="menu", locale=Locale.RU))


async def test_get_banner_image_raises_not_found_when_file_missing_on_disk(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    cfg = _config(config, tmp_path)
    upload_use_case = UploadBannerUseCase(
        banner_repository, translation_repository, cfg, uow, RecordingEventPublisher()
    )
    get_use_case = GetBannerImageUseCase(banner_repository, cfg, uow)

    await upload_use_case(
        OWNER,
        UploadBannerFileDto(
            name="menu", locale=Locale.RU, content_type="image/jpeg", data=FAKE_JPEG
        ),
    )
    (tmp_path / "banners" / "menu_ru.jpg").unlink()

    with pytest.raises(NotFoundError):
        await get_use_case(OWNER, BannerKeyDto(name="menu", locale=Locale.RU))


async def test_upload_rejects_content_not_matching_declared_type(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    use_case = UploadBannerUseCase(
        banner_repository,
        translation_repository,
        _config(config, tmp_path),
        uow,
        RecordingEventPublisher(),
    )

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UploadBannerFileDto(
                name="menu",
                locale=Locale.RU,
                content_type="image/jpeg",
                data=b"this is not actually a jpeg",
            ),
        )


async def test_upload_replaces_file_when_format_changes(
    banner_repository: BannerRepository,
    translation_repository: TranslationRepository,
    config: AppConfig,
    uow: UnitOfWork,
    tmp_path: Path,
) -> None:
    await _seed_locales(translation_repository)
    cfg = _config(config, tmp_path)
    use_case = UploadBannerUseCase(
        banner_repository, translation_repository, cfg, uow, RecordingEventPublisher()
    )

    await use_case(
        OWNER,
        UploadBannerFileDto(
            name="menu", locale=Locale.RU, content_type="image/jpeg", data=FAKE_JPEG
        ),
    )
    assert (tmp_path / "banners" / "menu_ru.jpg").exists()

    banner = await use_case(
        OWNER,
        UploadBannerFileDto(name="menu", locale=Locale.RU, content_type="image/png", data=FAKE_PNG),
    )

    assert banner.extension == "png"
    assert not (tmp_path / "banners" / "menu_ru.jpg").exists()
    assert (tmp_path / "banners" / "menu_ru.png").read_bytes() == FAKE_PNG
