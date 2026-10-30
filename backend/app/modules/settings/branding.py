from typing import Any, Final, Optional

from app.core.enums import AppearanceImageKind, AppearanceTarget
from app.modules.settings.dto import AppearanceSettingsDto

_DEFAULT_NAME: Final[str] = "Remnashop"
_DEFAULT_COLOR: Final[str] = "#111111"
_SVG: Final[str] = "image/svg+xml"


def _raster_images(
    cabinet: AppearanceSettingsDto, dashboard: AppearanceSettingsDto
) -> list[tuple[str, str]]:
    """(path, content type) of non-SVG branding images, favicons first, cabinet first."""
    images: list[tuple[str, str]] = []
    for kind in (AppearanceImageKind.FAVICON, AppearanceImageKind.LOGO):
        for target, dto in (
            (AppearanceTarget.CABINET, cabinet),
            (AppearanceTarget.DASHBOARD, dashboard),
        ):
            content_type = (
                dto.favicon_content_type
                if kind is AppearanceImageKind.FAVICON
                else dto.logo_content_type
            )
            if content_type is None or content_type == _SVG or dto.updated_at is None:
                continue
            version = int(dto.updated_at.timestamp())
            images.append((f"/api/appearance/{target}/{kind}?v={version}", content_type))
    return images


def push_icon_path(
    cabinet: AppearanceSettingsDto, dashboard: AppearanceSettingsDto
) -> Optional[str]:
    images = _raster_images(cabinet, dashboard)
    return images[0][0] if images else None


def cabinet_manifest(
    cabinet: AppearanceSettingsDto, dashboard: AppearanceSettingsDto
) -> dict[str, Any]:
    name = cabinet.brand_name or dashboard.brand_name or _DEFAULT_NAME
    return {
        "name": name,
        "short_name": name,
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": _DEFAULT_COLOR,
        "theme_color": cabinet.primary_color or dashboard.primary_color or _DEFAULT_COLOR,
        "icons": [
            *(
                {"src": path, "sizes": "any", "type": ct}
                for path, ct in _raster_images(cabinet, dashboard)
            ),
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
