"""The catalog a shop has until its owner saves one: the common apps per platform, ru/en texts.

Built through the same models as a dashboard write: a broken default fails at import, not in a
cabinet.
"""

from typing import Final

from app.core.enums import Locale
from app.modules.connect_guide.catalog import (
    SUBSCRIPTION_LINK_TOKEN,
    ConnectApp,
    ConnectCatalog,
    ConnectPlatform,
    ConnectStep,
    CopyLinkButton,
    DeepLinkButton,
    ExternalButton,
    PlatformId,
)

_HAPP_APPLE: Final[str] = "https://apps.apple.com/app/happ-proxy-utility/id6504287215"
_HAPP_APPLE_TV: Final[str] = "https://apps.apple.com/app/happ-proxy-utility-for-tv/id6748297274"
_HAPP_GOOGLE: Final[str] = "https://play.google.com/store/apps/details?id=com.happproxy"
_HAPP_DESKTOP: Final[str] = "https://github.com/Happ-proxy/happ-desktop/releases/latest"
_V2RAYTUN_APPLE: Final[str] = "https://apps.apple.com/app/v2raytun/id6476628951"
_V2RAYTUN_GOOGLE: Final[str] = "https://play.google.com/store/apps/details?id=com.v2raytun.android"
_HIDDIFY_APPLE: Final[str] = "https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532"
_HIDDIFY_GOOGLE: Final[str] = "https://play.google.com/store/apps/details?id=app.hiddify.com"
_HIDDIFY_DESKTOP: Final[str] = "https://github.com/hiddify/hiddify-app/releases/latest"
_FLCLASHX_DESKTOP: Final[str] = "https://github.com/pluralplay/FlClashX/releases/latest"


def _text(ru: str, en: str) -> dict[Locale, str]:
    return {Locale.RU: ru, Locale.EN: en}


def _app(
    app_id: str,
    name: str,
    store: str,
    deep_link: str,
    featured: bool = False,
) -> ConnectApp:
    return ConnectApp(
        id=app_id,
        name=name,
        featured=featured,
        steps=[
            ConnectStep(
                title=_text(f"Установите {name}", f"Install {name}"),
                body=_text(
                    "Скачайте приложение и откройте его один раз.",
                    "Download the app and open it once.",
                ),
                icon="download",
                buttons=[
                    ExternalButton(kind="external", label=_text("Скачать", "Download"), url=store)
                ],
            ),
            ConnectStep(
                title=_text("Добавьте подписку", "Add the subscription"),
                body=_text(
                    "Нажмите «Добавить» — приложение откроется с вашей подпиской. "
                    "Если не открылось, скопируйте ссылку и добавьте её в приложении вручную.",
                    "Tap “Add” and the app opens with your subscription. "
                    "If it doesn't, copy the link and add it in the app by hand.",
                ),
                icon="plus",
                buttons=[
                    DeepLinkButton(
                        kind="deep_link",
                        label=_text("Добавить", "Add"),
                        template=deep_link,
                    ),
                    CopyLinkButton(
                        kind="copy_link", label=_text("Скопировать ссылку", "Copy link")
                    ),
                ],
            ),
            ConnectStep(
                title=_text("Подключитесь", "Connect"),
                body=_text(
                    "Выберите сервер и нажмите кнопку включения в приложении.",
                    "Pick a server and tap the power button in the app.",
                ),
                icon="power",
            ),
        ],
    )


_LINK: Final[str] = SUBSCRIPTION_LINK_TOKEN


def _happ(store: str) -> ConnectApp:
    return _app("happ", "Happ", store, f"happ://add/{_LINK}", featured=True)


def _platform(platform_id: PlatformId, *apps: ConnectApp) -> ConnectPlatform:
    return ConnectPlatform(id=platform_id, apps=list(apps))


DEFAULT_CATALOG: Final[ConnectCatalog] = ConnectCatalog(
    platforms=[
        _platform(
            "ios",
            _happ(_HAPP_APPLE),
            _app("v2raytun", "v2RayTun", _V2RAYTUN_APPLE, f"v2raytun://import/{_LINK}"),
        ),
        _platform(
            "android",
            _happ(_HAPP_GOOGLE),
            _app("v2raytun", "v2RayTun", _V2RAYTUN_GOOGLE, f"v2raytun://import/{_LINK}"),
            _app("hiddify", "Hiddify", _HIDDIFY_GOOGLE, f"hiddify://import/{_LINK}"),
        ),
        _platform(
            "windows",
            _happ(_HAPP_DESKTOP),
            _app("hiddify", "Hiddify", _HIDDIFY_DESKTOP, f"hiddify://import/{_LINK}"),
            _app(
                "flclashx",
                "FlClashX",
                _FLCLASHX_DESKTOP,
                f"flclashx://install-config?url={_LINK}",
            ),
        ),
        _platform(
            "macos",
            _happ(_HAPP_APPLE),
            _app("hiddify", "Hiddify", _HIDDIFY_APPLE, f"hiddify://import/{_LINK}"),
        ),
        _platform(
            "linux",
            _app(
                "hiddify", "Hiddify", _HIDDIFY_DESKTOP, f"hiddify://import/{_LINK}", featured=True
            ),
            _app(
                "flclashx",
                "FlClashX",
                _FLCLASHX_DESKTOP,
                f"flclashx://install-config?url={_LINK}",
            ),
        ),
        _platform("androidtv", _happ(_HAPP_GOOGLE)),
        _platform("appletv", _happ(_HAPP_APPLE_TV)),
    ]
)
