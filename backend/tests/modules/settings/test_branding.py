from datetime import datetime, timezone
from typing import Optional

from app.modules.settings import AppearanceSettingsDto
from app.modules.settings.branding import cabinet_manifest, push_icon_path

_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
_V = int(_AT.timestamp())


def _dto(
    *,
    logo: Optional[str] = None,
    favicon: Optional[str] = None,
    brand_name: Optional[str] = None,
    primary_color: Optional[str] = None,
) -> AppearanceSettingsDto:
    return AppearanceSettingsDto(
        brand_name=brand_name,
        primary_color=primary_color,
        has_logo=logo is not None,
        has_favicon=favicon is not None,
        logo_content_type=logo,
        favicon_content_type=favicon,
        updated_at=_AT,
    )


def test_icon_prefers_cabinet_favicon() -> None:
    cabinet = _dto(favicon="image/png", logo="image/png")
    dashboard = _dto(favicon="image/png")

    assert push_icon_path(cabinet, dashboard) == f"/api/appearance/cabinet/favicon?v={_V}"


def test_icon_falls_back_to_dashboard_favicon() -> None:
    assert (
        push_icon_path(_dto(), _dto(favicon="image/png"))
        == f"/api/appearance/dashboard/favicon?v={_V}"
    )


def test_icon_skips_svg() -> None:
    cabinet = _dto(favicon="image/svg+xml")
    dashboard = _dto(logo="image/png")

    assert push_icon_path(cabinet, dashboard) == f"/api/appearance/dashboard/logo?v={_V}"


def test_icon_none_when_only_svg() -> None:
    svg = _dto(favicon="image/svg+xml", logo="image/svg+xml")

    assert push_icon_path(svg, svg) is None


def test_manifest_defaults_without_appearance() -> None:
    manifest = cabinet_manifest(_dto(), _dto())

    assert manifest["name"] == manifest["short_name"] == "Remnashop"
    assert manifest["theme_color"] == "#111111"
    assert manifest["icons"] == [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
    ]


def test_manifest_uses_brand_and_color() -> None:
    cabinet = _dto(brand_name="Acme", primary_color="#ff0000", favicon="image/webp")
    dashboard = _dto(brand_name="Panel", primary_color="#00ff00", logo="image/png")

    manifest = cabinet_manifest(cabinet, dashboard)

    assert manifest["name"] == manifest["short_name"] == "Acme"
    assert manifest["theme_color"] == "#ff0000"
    assert [i["src"] for i in manifest["icons"]] == [
        f"/api/appearance/cabinet/favicon?v={_V}",
        f"/api/appearance/dashboard/logo?v={_V}",
        "/icon-192.png",
        "/icon-512.png",
    ]
    assert manifest["icons"][0] == {
        "src": f"/api/appearance/cabinet/favicon?v={_V}",
        "sizes": "any",
        "type": "image/webp",
    }
    assert manifest["start_url"] == manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["background_color"] == "#111111"


def test_manifest_falls_back_to_dashboard_brand() -> None:
    manifest = cabinet_manifest(_dto(), _dto(brand_name="Panel", primary_color="#00ff00"))

    assert manifest["name"] == "Panel"
    assert manifest["theme_color"] == "#00ff00"
