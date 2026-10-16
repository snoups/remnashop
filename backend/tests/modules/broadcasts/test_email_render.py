from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.enums import BroadcastCategory, Locale
from app.modules.broadcasts.dto import (
    BroadcastAudienceDto,
    BroadcastContentDto,
    BroadcastDto,
    BroadcastEmailContentDto,
    RecipientContextDto,
)
from app.modules.broadcasts.email_render import (
    BroadcastEmailRenderer,
    UnsubscribeLinks,
    unsubscribe_links,
)
from app.modules.email import EmailBrandDto

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
SECRET = "k" * 32
BRAND = EmailBrandDto(brand="Shop", color="#112233", has_logo=False)


def _broadcast(**overrides: object) -> BroadcastDto:
    values: dict[str, object] = {
        "id": 7,
        "status": "SENDING",
        "category": BroadcastCategory.SERVICE,
        "audience": BroadcastAudienceDto(),
        "default_locale": Locale.EN,
        "contents": {Locale.EN: BroadcastContentDto(text="x", button_labels=[])},
        "buttons": [],
        "email_contents": {
            Locale.EN: BroadcastEmailContentDto(
                subject="Hi { $name }", html='<p>{ $plan }</p><img src="bc-image:3">'
            )
        },
    }
    values.update(overrides)
    return BroadcastDto.model_validate(values)


def _ctx(language: Locale = Locale.EN, **overrides: object) -> RecipientContextDto:
    values: dict[str, object] = {
        "user_id": 5,
        "name": "Ann",
        "username": None,
        "language": language,
        "bonus_days": 0,
        "points": 0,
        "plan_name": "Pro",
        "expire_at": NOW + timedelta(days=3),
    }
    values.update(overrides)
    return RecipientContextDto(**values)  # type: ignore[arg-type]


def _renderer(
    broadcast: BroadcastDto,
    unsubscribe: Optional[UnsubscribeLinks] = None,
    labels: Optional[dict[Locale, str]] = None,
) -> BroadcastEmailRenderer:
    return BroadcastEmailRenderer(
        broadcast,
        promocode_code=None,
        brand=BRAND,
        unsubscribe=unsubscribe,
        unsubscribe_labels=labels or {},
        image_src=lambda i: f"cid:img-{i}",
    )


def test_renders_subject_body_and_images() -> None:
    rendered = _renderer(_broadcast()).render(_ctx(), NOW)
    assert rendered.subject == "Hi Ann"
    assert "Pro" in rendered.html
    assert 'src="cid:img-3"' in rendered.html
    assert rendered.image_ids == {3}
    assert "Pro" in rendered.text


def test_variables_escaped_in_body_subject_is_plain_one_line() -> None:
    rendered = _renderer(_broadcast()).render(_ctx(name="<b>x</b>\r\nBcc: a@b"), NOW)
    assert rendered.subject == "Hi <b>x</b> Bcc: a@b"
    broadcast = _broadcast(
        email_contents={Locale.EN: BroadcastEmailContentDto(subject="s", html="<p>{ $name }</p>")}
    )
    html = _renderer(broadcast).render(_ctx(name="<b>x</b>"), NOW).html
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>x</b>" not in html


def test_empty_value_becomes_dash() -> None:
    rendered = _renderer(_broadcast()).render(_ctx(plan_name=None), NOW)
    assert rendered.text == "—"


def test_premium_emoji_becomes_glyph() -> None:
    broadcast = _broadcast(
        email_contents={
            Locale.EN: BroadcastEmailContentDto(
                subject="[🔥](emoji:123) sale", html="<p>[🔥](emoji:123) go</p>"
            )
        }
    )
    rendered = _renderer(broadcast).render(_ctx(), NOW)
    assert rendered.subject == "🔥 sale"
    assert "🔥 go" in rendered.html
    assert "tg-emoji" not in rendered.html
    assert "emoji:" not in rendered.html


def test_marketing_adds_unsubscribe_footer_and_headers() -> None:
    links = unsubscribe_links("https://cab.example/", SECRET)
    rendered = _renderer(
        _broadcast(category=BroadcastCategory.MARKETING), links, {Locale.EN: "Stop"}
    ).render(_ctx(), NOW)
    assert 'href="https://cab.example/unsubscribe?token=5.' in rendered.html
    assert ">Stop</a>" in rendered.html
    assert rendered.headers["List-Unsubscribe"].startswith(
        "<https://cab.example/api/unsubscribe?token=5."
    )
    assert rendered.headers["List-Unsubscribe"].endswith(">")
    assert rendered.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "Stop: https://cab.example/unsubscribe?token=5." in rendered.text


def test_service_has_no_unsubscribe() -> None:
    links = unsubscribe_links("https://cab.example", SECRET)
    rendered = _renderer(_broadcast(), links).render(_ctx(), NOW)
    assert rendered.headers == {}
    assert "unsubscribe" not in rendered.html.lower()


def test_falls_back_to_default_locale() -> None:
    assert _renderer(_broadcast()).render(_ctx(Locale.RU), NOW).subject == "Hi Ann"
