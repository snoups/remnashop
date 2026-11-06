from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.core.enums import BroadcastButtonKind, BroadcastCategory, BroadcastDelivery, Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.utils.telegram_text import TELEGRAM_TEXT_LIMIT
from app.modules.broadcasts.dto import (
    BroadcastAudienceDto,
    BroadcastButtonDto,
    BroadcastContentDto,
    BroadcastEmailContentDto,
    SaveBroadcastDto,
)
from app.modules.broadcasts.validation import (
    validate_audience,
    validate_broadcast,
    validate_text_lengths,
)


def _data(**overrides: object) -> SaveBroadcastDto:
    base = SaveBroadcastDto(
        category=BroadcastCategory.SERVICE,
        audience=BroadcastAudienceDto(),
        default_locale=Locale.EN,
        contents={Locale.EN: BroadcastContentDto(text="Hello { $name }")},
        buttons=[],
        promocode_id=None,
        post_to_channel=False,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def _code(call: object) -> ErrorCode:
    with pytest.raises(ValidationError) as error:
        call()  # type: ignore[operator]
    return error.value.code


def test_valid_broadcast_passes() -> None:
    validate_broadcast(_data(), has_media=False, images={})


def test_default_locale_must_have_text() -> None:
    data = _data(contents={Locale.RU: BroadcastContentDto(text="Привет")})
    expected = ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING
    assert _code(lambda: validate_broadcast(data, has_media=False, images={})) is expected


def test_unknown_variable() -> None:
    data = _data(contents={Locale.EN: BroadcastContentDto(text="{ $balance }")})
    expected = ErrorCode.BROADCAST_VARIABLE_UNKNOWN
    assert _code(lambda: validate_broadcast(data, has_media=False, images={})) is expected


def test_caption_limit_with_media() -> None:
    data = _data(contents={Locale.EN: BroadcastContentDto(text="x" * 1025)})
    validate_broadcast(data, has_media=False, images={})
    expected = ErrorCode.BROADCAST_TEXT_TOO_LONG
    assert _code(lambda: validate_broadcast(data, has_media=True, images={})) is expected


def test_promocode_variable_requires_promocode() -> None:
    data = _data(contents={Locale.EN: BroadcastContentDto(text="Code { $promocode }")})
    expected = ErrorCode.BROADCAST_PROMOCODE_REQUIRED
    assert _code(lambda: validate_broadcast(data, has_media=False, images={})) is expected


def test_promocode_button_requires_promocode() -> None:
    data = _data(
        buttons=[BroadcastButtonDto(kind=BroadcastButtonKind.PROMOCODE)],
        contents={Locale.EN: BroadcastContentDto(text="x", button_labels=["Get"])},
    )
    expected = ErrorCode.BROADCAST_PROMOCODE_REQUIRED
    assert _code(lambda: validate_broadcast(data, has_media=False, images={})) is expected


@pytest.mark.parametrize(
    "buttons,labels",
    [
        ([BroadcastButtonDto(kind=BroadcastButtonKind.MENU)], []),
        ([BroadcastButtonDto(kind=BroadcastButtonKind.URL, url="ftp://x")], ["a"]),
        ([BroadcastButtonDto(kind=BroadcastButtonKind.URL, url="https://a b")], ["a"]),
        ([BroadcastButtonDto(kind=BroadcastButtonKind.MENU)] * 11, ["a"] * 11),
        ([BroadcastButtonDto(kind=BroadcastButtonKind.MENU)], [" "]),
    ],
)
def test_invalid_buttons(buttons: list[BroadcastButtonDto], labels: list[str]) -> None:
    content = BroadcastContentDto(text="x", button_labels=labels)
    data = _data(buttons=buttons, contents={Locale.EN: content})
    expected = ErrorCode.BROADCAST_BUTTONS_INVALID
    assert _code(lambda: validate_broadcast(data, has_media=False, images={})) is expected


def test_channel_post_rejects_personal_variables() -> None:
    data = _data(post_to_channel=True)
    expected = ErrorCode.BROADCAST_CHANNEL_PERSONAL_VARIABLES
    assert _code(lambda: validate_broadcast(data, has_media=False, images={})) is expected


def test_empty_text_allowed_only_with_media() -> None:
    data = _data(contents={Locale.EN: BroadcastContentDto(text="  ")})
    validate_broadcast(data, has_media=True, images={})
    expected = ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING
    assert _code(lambda: validate_broadcast(data, has_media=False, images={})) is expected


_UTC = timezone.utc


@pytest.mark.parametrize(
    "audience",
    [
        BroadcastAudienceDto(plan_ids=[0]),
        BroadcastAudienceDto(user_ids=[-1]),
        BroadcastAudienceDto(expires_within_days=0),
        BroadcastAudienceDto(not_connected_within_days=0),
        BroadcastAudienceDto(not_connected_within_days=31),
        BroadcastAudienceDto(registered_from=datetime(2026, 1, 1, tzinfo=_UTC)),
        BroadcastAudienceDto(
            registered_from=datetime(2026, 2, 1, tzinfo=_UTC),
            registered_to=datetime(2026, 1, 1, tzinfo=_UTC),
        ),
        BroadcastAudienceDto(user_ids=list(range(1, 10_002))),
    ],
)
def test_invalid_audience(audience: BroadcastAudienceDto) -> None:
    expected = ErrorCode.BROADCAST_AUDIENCE_INVALID
    assert _code(lambda: validate_audience(audience)) is expected


def test_blank_non_default_locale_is_rejected() -> None:
    data = _data(
        contents={
            Locale.EN: BroadcastContentDto(text="Hello"),
            Locale.RU: BroadcastContentDto(text="  "),
        }
    )
    expected = ErrorCode.BROADCAST_TEXT_EMPTY
    assert _code(lambda: validate_broadcast(data, has_media=False, images={})) is expected


save_dto = _data
EMAIL = {Locale.EN: BroadcastEmailContentDto(subject="Hi { $name }", html="<p>Body</p>")}


def test_email_mode_needs_no_telegram_text() -> None:
    validate_broadcast(
        save_dto(delivery=BroadcastDelivery.EMAIL, contents={}, email_contents=EMAIL),
        has_media=False,
        images={},
    )


def test_email_mode_needs_default_locale_email() -> None:
    with pytest.raises(ValidationError) as caught:
        validate_broadcast(
            save_dto(delivery=BroadcastDelivery.EMAIL, contents={}), has_media=False, images={}
        )
    assert caught.value.code is ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING


def test_fallback_needs_email_content() -> None:
    with pytest.raises(ValidationError):
        validate_broadcast(save_dto(email_fallback=True), has_media=False, images={})


@pytest.mark.parametrize(
    "overrides",
    [
        {"delivery": BroadcastDelivery.EMAIL, "email_fallback": True},
        {"delivery": BroadcastDelivery.ALL, "email_fallback": True},
        {"delivery": BroadcastDelivery.EMAIL, "post_to_channel": True},
    ],
)
def test_options_outside_their_mode(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError) as caught:
        validate_broadcast(save_dto(email_contents=EMAIL, **overrides), has_media=False, images={})
    assert caught.value.code is ErrorCode.BROADCAST_DELIVERY_INVALID


def test_disabled_channel_content_kept_and_not_required() -> None:
    validate_broadcast(
        save_dto(
            delivery=BroadcastDelivery.EMAIL,
            contents={Locale.EN: BroadcastContentDto(text="")},
            email_contents=EMAIL,
        ),
        has_media=False,
        images={},
    )
    validate_broadcast(save_dto(email_contents=EMAIL), has_media=False, images={})


@pytest.mark.parametrize("subject", ["", "   ", "x" * 201])
def test_subject_required_and_bounded(subject: str) -> None:
    content = {Locale.EN: BroadcastEmailContentDto(subject=subject, html="<p>b</p>")}
    with pytest.raises(ValidationError) as caught:
        validate_broadcast(
            save_dto(delivery=BroadcastDelivery.EMAIL, contents={}, email_contents=content),
            has_media=False,
            images={},
        )
    assert caught.value.code is ErrorCode.BROADCAST_EMAIL_SUBJECT_INVALID


def test_stored_email_html_always_checked() -> None:
    bad = {Locale.EN: BroadcastEmailContentDto(subject="s", html="<script></script>")}
    with pytest.raises(ValidationError) as caught:
        validate_broadcast(save_dto(email_contents=bad), has_media=False, images={})
    assert caught.value.code is ErrorCode.BROADCAST_EMAIL_HTML_INVALID


def test_email_variables_checked() -> None:
    content = {Locale.EN: BroadcastEmailContentDto(subject="{ $nope }", html="<p>b</p>")}
    with pytest.raises(ValidationError) as caught:
        validate_broadcast(
            save_dto(delivery=BroadcastDelivery.EMAIL, contents={}, email_contents=content),
            has_media=False,
            images={},
        )
    assert caught.value.code is ErrorCode.BROADCAST_VARIABLE_UNKNOWN


def test_email_promocode_variable_needs_promocode() -> None:
    content = {Locale.EN: BroadcastEmailContentDto(subject="s", html="<p>{ $promocode }</p>")}
    with pytest.raises(ValidationError) as caught:
        validate_broadcast(
            save_dto(delivery=BroadcastDelivery.EMAIL, contents={}, email_contents=content),
            has_media=False,
            images={},
        )
    assert caught.value.code is ErrorCode.BROADCAST_PROMOCODE_REQUIRED


def test_unknown_image_rejected() -> None:
    content = {Locale.EN: BroadcastEmailContentDto(subject="s", html='<img src="bc-image:5">')}
    with pytest.raises(ValidationError) as caught:
        validate_broadcast(
            save_dto(delivery=BroadcastDelivery.EMAIL, contents={}, email_contents=content),
            has_media=False,
            images={},
        )
    assert caught.value.code is ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID


def test_letter_image_budget() -> None:
    html = "".join(f'<img src="bc-image:{i}">' for i in (1, 2, 3, 4))
    content = {Locale.EN: BroadcastEmailContentDto(subject="s", html=html)}
    images = dict.fromkeys((1, 2, 3, 4), 900 * 1024)  # 3.5 MB in one letter
    with pytest.raises(ValidationError) as caught:
        validate_broadcast(
            save_dto(delivery=BroadcastDelivery.EMAIL, contents={}, email_contents=content),
            has_media=False,
            images=images,
        )
    assert caught.value.code is ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID


def test_telegram_delivery_needs_default_locale_text() -> None:
    with pytest.raises(ValidationError) as caught:
        validate_broadcast(save_dto(contents={}), has_media=False, images={})
    assert caught.value.code is ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING


def test_text_length_counts_each_variable_at_its_longest() -> None:
    # fits as written, but not once a 64-character name is in
    text = "x" * (TELEGRAM_TEXT_LIMIT - 20) + "{ $name }"

    with pytest.raises(ValidationError) as error:
        validate_text_lengths({Locale.EN: BroadcastContentDto(text=text)}, has_media=False)

    assert error.value.code is ErrorCode.BROADCAST_TEXT_TOO_LONG
