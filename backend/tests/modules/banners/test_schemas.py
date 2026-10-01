from app.core.enums import Locale
from app.modules.banners.api.schemas import BannerMetaResponse


def test_banner_meta_response_carries_fields() -> None:
    response = BannerMetaResponse(
        name="menu", locale=Locale.RU, content_type="image/jpeg", size_bytes=1234
    )
    assert response.name == "menu"
    assert response.size_bytes == 1234
