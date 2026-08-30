from app.core.enums import BannerName, Locale
from app.modules.banners.api.schemas import BannerListResponse, BannerMetaResponse


def test_banner_meta_response_carries_fields() -> None:
    response = BannerMetaResponse(
        name=BannerName.MENU, locale=Locale.RU, content_type="image/jpeg", size_bytes=1234
    )
    assert response.name == BannerName.MENU
    assert response.size_bytes == 1234


def test_banner_list_response_carries_available_locales() -> None:
    response = BannerListResponse(banners=[], available_locales=[Locale.EN, Locale.RU])
    assert response.available_locales == [Locale.EN, Locale.RU]
