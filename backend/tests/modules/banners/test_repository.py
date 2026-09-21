from app.core.constants import DEFAULT_BANNER_NAME
from app.core.enums import Locale
from app.modules.banners.dto import UploadBannerDto
from app.modules.banners.repository import BannerRepository


async def test_get_returns_none_when_missing(banner_repository: BannerRepository) -> None:
    banner = await banner_repository.get("menu", Locale.RU)
    assert banner is None


async def test_upsert_then_get_roundtrips(banner_repository: BannerRepository) -> None:
    await banner_repository.upsert(
        UploadBannerDto(
            name="menu",
            locale=Locale.RU,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=1234,
        )
    )

    banner = await banner_repository.get("menu", Locale.RU)
    assert banner is not None
    assert banner.content_type == "image/jpeg"
    assert banner.extension == "jpg"
    assert banner.size_bytes == 1234


async def test_upsert_replaces_existing_row(banner_repository: BannerRepository) -> None:
    await banner_repository.upsert(
        UploadBannerDto(
            name="menu",
            locale=Locale.RU,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=100,
        )
    )
    await banner_repository.upsert(
        UploadBannerDto(
            name="menu",
            locale=Locale.RU,
            content_type="image/png",
            extension="png",
            size_bytes=200,
        )
    )

    banner = await banner_repository.get("menu", Locale.RU)
    assert banner is not None
    assert banner.content_type == "image/png"
    assert banner.size_bytes == 200


async def test_list_all_returns_every_row(banner_repository: BannerRepository) -> None:
    await banner_repository.upsert(
        UploadBannerDto(
            name="menu",
            locale=Locale.RU,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=1,
        )
    )
    await banner_repository.upsert(
        UploadBannerDto(
            name=DEFAULT_BANNER_NAME,
            locale=Locale.EN,
            content_type="image/png",
            extension="png",
            size_bytes=1,
        )
    )

    banners = await banner_repository.list_all()
    assert len(banners) == 2


async def test_delete_removes_row(banner_repository: BannerRepository) -> None:
    await banner_repository.upsert(
        UploadBannerDto(
            name="menu",
            locale=Locale.RU,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=1,
        )
    )
    await banner_repository.delete("menu", Locale.RU)

    assert await banner_repository.get("menu", Locale.RU) is None


async def test_delete_missing_row_does_not_raise(banner_repository: BannerRepository) -> None:
    await banner_repository.delete("menu", Locale.RU)


async def test_find_for_display_exact_match(banner_repository: BannerRepository) -> None:
    await banner_repository.upsert(
        UploadBannerDto(
            name="menu",
            locale=Locale.RU,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=1,
        )
    )

    banner = await banner_repository.find_for_display("menu", Locale.RU, Locale.EN)
    assert banner is not None
    assert banner.locale == Locale.RU


async def test_find_for_display_falls_back_to_default_name_same_locale(
    banner_repository: BannerRepository,
) -> None:
    await banner_repository.upsert(
        UploadBannerDto(
            name=DEFAULT_BANNER_NAME,
            locale=Locale.RU,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=1,
        )
    )

    banner = await banner_repository.find_for_display("menu", Locale.RU, Locale.EN)
    assert banner is not None
    assert banner.name == DEFAULT_BANNER_NAME
    assert banner.locale == Locale.RU


async def test_find_for_display_falls_back_to_requested_name_default_locale(
    banner_repository: BannerRepository,
) -> None:
    await banner_repository.upsert(
        UploadBannerDto(
            name="menu",
            locale=Locale.EN,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=1,
        )
    )

    banner = await banner_repository.find_for_display("menu", Locale.RU, Locale.EN)
    assert banner is not None
    assert banner.name == "menu"
    assert banner.locale == Locale.EN


async def test_find_for_display_falls_back_to_default_name_default_locale(
    banner_repository: BannerRepository,
) -> None:
    await banner_repository.upsert(
        UploadBannerDto(
            name=DEFAULT_BANNER_NAME,
            locale=Locale.EN,
            content_type="image/jpeg",
            extension="jpg",
            size_bytes=1,
        )
    )

    banner = await banner_repository.find_for_display("menu", Locale.RU, Locale.EN)
    assert banner is not None
    assert banner.name == DEFAULT_BANNER_NAME
    assert banner.locale == Locale.EN


async def test_find_for_display_returns_none_when_nothing_matches(
    banner_repository: BannerRepository,
) -> None:
    banner = await banner_repository.find_for_display("menu", Locale.RU, Locale.EN)
    assert banner is None
