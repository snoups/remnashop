from app.core.constants import ASSETS_DIR
from app.core.enums import Locale, SubscriptionStatus
from app.telegram.dialogs.rendering import render_window_text
from app.telegram.i18n import build_translator_hub


def _card(**kwargs: object) -> str:
    text = (ASSETS_DIR / "translations" / "en" / "menu.ftl").read_text()
    hub = build_translator_hub([Locale.EN], {Locale.EN: text}, Locale.EN)
    runner = hub.get_translator_by_locale(Locale.EN.value)
    args: dict[str, object] = {
        "plan_name": "Pro",
        "status": SubscriptionStatus.ACTIVE.value,
        "is_trial": 0,
        "expire_at": "01.01.2027",
        "traffic_limit": 0,
        "device_limit": 0,
    }
    text = runner.get("msg-subscription-card", **{**args, **kwargs})
    return text.replace("\u2068", "").replace("\u2069", "")


def test_card_shows_localized_status_and_unlimited_limits() -> None:
    text = _card()

    assert "<b>Status</b>: 🟢 Active" in text
    assert "<b>Traffic limit</b>: Unlimited" in text
    assert "<b>Device limit</b>: Unlimited" in text


def test_card_shows_limits_with_units() -> None:
    text = _card(traffic_limit=50, device_limit=3)

    assert "<b>Traffic limit</b>: 50 GB" in text
    assert "<b>Device limit</b>: 3" in text


def _rendered(**kwargs: object) -> str:
    text = (ASSETS_DIR / "translations" / "en" / "menu.ftl").read_text()
    hub = build_translator_hub([Locale.EN], {Locale.EN: text}, Locale.EN)
    args: dict[str, object] = {
        "plan_name": "Pro",
        "status": SubscriptionStatus.ACTIVE.value,
        "is_trial": 0,
        "expire_at": "01.01.2027",
        "traffic_limit": 50,
        "device_limit": 3,
    }
    runner = hub.get_translator_by_locale(Locale.EN.value)
    return render_window_text(runner, "msg-subscription-card", **{**args, **kwargs})


def test_card_names_a_trial() -> None:
    assert _rendered(is_trial=1).startswith("<b>🎁 Trial subscription · Pro</b>")
    assert _rendered().startswith("<b>💳 Subscription · Pro</b>")
