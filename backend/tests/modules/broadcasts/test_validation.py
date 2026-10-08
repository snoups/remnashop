from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.core.enums import BroadcastButtonKind, BroadcastCategory, Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.broadcasts.dto import (
    BroadcastAudienceDto,
    BroadcastButtonDto,
    BroadcastContentDto,
    SaveBroadcastDto,
)
from app.modules.broadcasts.validation import validate_audience, validate_broadcast


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
    validate_broadcast(_data(), has_media=False)


def test_default_locale_must_have_text() -> None:
    data = _data(contents={Locale.RU: BroadcastContentDto(text="Привет")})
    expected = ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING
    assert _code(lambda: validate_broadcast(data, has_media=False)) is expected


def test_unknown_variable() -> None:
    data = _data(contents={Locale.EN: BroadcastContentDto(text="{ $balance }")})
    expected = ErrorCode.BROADCAST_VARIABLE_UNKNOWN
    assert _code(lambda: validate_broadcast(data, has_media=False)) is expected


def test_caption_limit_with_media() -> None:
    data = _data(contents={Locale.EN: BroadcastContentDto(text="x" * 1025)})
    validate_broadcast(data, has_media=False)
    expected = ErrorCode.BROADCAST_TEXT_TOO_LONG
    assert _code(lambda: validate_broadcast(data, has_media=True)) is expected


def test_promocode_variable_requires_promocode() -> None:
    data = _data(contents={Locale.EN: BroadcastContentDto(text="Code { $promocode }")})
    expected = ErrorCode.BROADCAST_PROMOCODE_REQUIRED
    assert _code(lambda: validate_broadcast(data, has_media=False)) is expected


def test_promocode_button_requires_promocode() -> None:
    data = _data(
        buttons=[BroadcastButtonDto(kind=BroadcastButtonKind.PROMOCODE)],
        contents={Locale.EN: BroadcastContentDto(text="x", button_labels=["Get"])},
    )
    expected = ErrorCode.BROADCAST_PROMOCODE_REQUIRED
    assert _code(lambda: validate_broadcast(data, has_media=False)) is expected


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
    assert _code(lambda: validate_broadcast(data, has_media=False)) is expected


def test_channel_post_rejects_personal_variables() -> None:
    data = _data(post_to_channel=True)
    expected = ErrorCode.BROADCAST_CHANNEL_PERSONAL_VARIABLES
    assert _code(lambda: validate_broadcast(data, has_media=False)) is expected


def test_empty_text_allowed_only_with_media() -> None:
    data = _data(contents={Locale.EN: BroadcastContentDto(text="  ")})
    validate_broadcast(data, has_media=True)
    expected = ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING
    assert _code(lambda: validate_broadcast(data, has_media=False)) is expected


_UTC = timezone.utc


@pytest.mark.parametrize(
    "audience",
    [
        BroadcastAudienceDto(plan_ids=[0]),
        BroadcastAudienceDto(user_ids=[-1]),
        BroadcastAudienceDto(expires_within_days=0),
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
    assert _code(lambda: validate_broadcast(data, has_media=False)) is expected
