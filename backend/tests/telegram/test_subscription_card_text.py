from app.core.constants import ASSETS_DIR
from app.core.enums import Locale, SubscriptionStatus
from app.telegram.i18n import build_translator_hub


def _card(**kwargs: object) -> str:
    text = (ASSETS_DIR / "translations" / "en" / "menu.ftl").read_text()
    hub = build_translator_hub([Locale.EN], {Locale.EN: text}, Locale.EN)
    runner = hub.get_translator_by_locale(Locale.EN.value)
    args: dict[str, object] = {
        "plan_name": "Pro",
        "status": SubscriptionStatus.ACTIVE.value,
        "expire_at": "01.01.2027",
        "traffic_limit": 0,
        "device_limit": 0,
    }
    text = runner.get("msg-subscription-card", **{**args, **kwargs})
    return text.replace("\u2068", "").replace("\u2069", "")


def test_card_shows_localized_status_and_unlimited_limits() -> None:
    text = _card()

    assert "Status: Active" in text
    assert "Traffic: Unlimited" in text
    assert "Devices: Unlimited" in text


def test_card_shows_limits_with_units() -> None:
    text = _card(traffic_limit=50, device_limit=3)

    assert "Traffic: 50 GB" in text
    assert "Devices: 3" in text
