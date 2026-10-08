from typing import TYPE_CHECKING, Final, Optional

from app.core.enums import BroadcastButtonKind, Locale
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.utils.telegram_text import (
    TELEGRAM_CAPTION_LIMIT,
    TELEGRAM_TEXT_LIMIT,
    telegram_length,
)
from app.modules.broadcasts.content import (
    BROADCAST_VARIABLES,
    CHANNEL_VARIABLES,
    used_variables,
    validate_html,
)
from app.modules.broadcasts.dto import (
    BroadcastAudienceDto,
    BroadcastButtonDto,
    BroadcastContentDto,
    SaveBroadcastDto,
)
from app.modules.promocodes import PromocodeRepository

if TYPE_CHECKING:
    from app.modules.broadcasts.repository import BroadcastRepository

MAX_TITLE_LENGTH: Final[int] = 120
MAX_BUTTONS: Final[int] = 10
MAX_BUTTON_LABEL_LENGTH: Final[int] = 64
MAX_USER_IDS: Final[int] = 10_000
MAX_FILTER_DAYS: Final[int] = 3650
_URL_SCHEMES: Final[tuple[str, ...]] = ("https://", "http://", "tg://")


def validate_text_lengths(contents: dict[Locale, BroadcastContentDto], *, has_media: bool) -> None:
    limit = TELEGRAM_CAPTION_LIMIT if has_media else TELEGRAM_TEXT_LIMIT
    for locale, content in contents.items():
        length = telegram_length(content.text)
        if length > limit:
            raise ValidationError(
                f"Text ({locale}) is {length} characters long, the limit is {limit}",
                code=ErrorCode.BROADCAST_TEXT_TOO_LONG,
            )


def _validate_texts_filled(contents: dict[Locale, BroadcastContentDto], *, has_media: bool) -> None:
    if has_media:
        return
    for locale, content in contents.items():
        if not content.text.strip():
            raise ValidationError(
                f"No text for locale {locale}", code=ErrorCode.BROADCAST_TEXT_EMPTY
            )


def _buttons_invalid(reason: str) -> ValidationError:
    return ValidationError(reason, code=ErrorCode.BROADCAST_BUTTONS_INVALID)


def _validate_button_url(url: str) -> None:
    if any(c.isspace() for c in url):
        raise _buttons_invalid(f"Invalid button URL: {url!r}")
    if not url.startswith(_URL_SCHEMES):
        raise _buttons_invalid(f"Invalid button URL: {url!r}")
    if url in _URL_SCHEMES:
        raise _buttons_invalid(f"Invalid button URL: {url!r}")


def _validate_button_labels(
    content: BroadcastContentDto, buttons: list[BroadcastButtonDto], locale: Locale
) -> None:
    if len(content.button_labels) != len(buttons):
        raise _buttons_invalid(f"Button labels ({locale}) don't match the buttons")
    for label in content.button_labels:
        if not label.strip() or len(label) > MAX_BUTTON_LABEL_LENGTH:
            raise _buttons_invalid(f"Button labels ({locale}) don't match the buttons")


def validate_texts(
    contents: dict[Locale, BroadcastContentDto], default_locale: Locale, *, has_media: bool
) -> BroadcastContentDto:
    default = contents.get(default_locale)
    if default is None or (not default.text.strip() and not has_media):
        raise ValidationError(
            f"No text for the default locale {default_locale}",
            code=ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING,
        )
    _validate_texts_filled(contents, has_media=has_media)
    return default


def validate_broadcast(data: SaveBroadcastDto, *, has_media: bool) -> None:
    if data.title is not None and len(data.title.strip()) > MAX_TITLE_LENGTH:
        raise ValidationError(
            f"Title is longer than {MAX_TITLE_LENGTH} characters",
            code=ErrorCode.BROADCAST_TITLE_TOO_LONG,
        )
    default = validate_texts(data.contents, data.default_locale, has_media=has_media)
    validate_text_lengths(data.contents, has_media=has_media)

    if len(data.buttons) > MAX_BUTTONS:
        raise _buttons_invalid(f"{len(data.buttons)} buttons, the limit is {MAX_BUTTONS}")
    for button in data.buttons:
        if button.kind is BroadcastButtonKind.URL:
            url = button.url or ""
            _validate_button_url(url)
        if button.kind is BroadcastButtonKind.PROMOCODE and data.promocode_id is None:
            raise ValidationError(
                "Promocode button without a promocode", code=ErrorCode.BROADCAST_PROMOCODE_REQUIRED
            )

    for locale, content in data.contents.items():
        validate_html(content.text)
        variables = used_variables(content.text)
        unknown = variables - BROADCAST_VARIABLES
        if unknown:
            raise ValidationError(
                f"Unknown variables ({locale}): {', '.join(sorted(unknown))}",
                code=ErrorCode.BROADCAST_VARIABLE_UNKNOWN,
            )
        if "promocode" in variables and data.promocode_id is None:
            raise ValidationError(
                "{ $promocode } without a promocode", code=ErrorCode.BROADCAST_PROMOCODE_REQUIRED
            )
        _validate_button_labels(content, data.buttons, locale)

    if data.post_to_channel and used_variables(default.text) - CHANNEL_VARIABLES:
        raise ValidationError(
            "A channel post can't contain personal variables",
            code=ErrorCode.BROADCAST_CHANNEL_PERSONAL_VARIABLES,
        )


def _audience_invalid(reason: str) -> ValidationError:
    return ValidationError(reason, code=ErrorCode.BROADCAST_AUDIENCE_INVALID)


def validate_audience(audience: BroadcastAudienceDto) -> None:
    if len(audience.user_ids) > MAX_USER_IDS:
        raise _audience_invalid(f"More than {MAX_USER_IDS} users")
    for ids in (audience.user_ids, audience.plan_ids, audience.ad_link_ids):
        if any(value <= 0 for value in ids):
            raise _audience_invalid("Ids must be positive")
    for days in (audience.expires_within_days, audience.expired_within_days):
        if days is not None and not 0 < days <= MAX_FILTER_DAYS:
            raise _audience_invalid(f"Days must be between 1 and {MAX_FILTER_DAYS}")
    if (audience.registered_from is None) != (audience.registered_to is None):
        raise _audience_invalid("registered_from and registered_to go together")
    if (
        audience.registered_from is not None
        and audience.registered_to is not None
        and audience.registered_from > audience.registered_to
    ):
        raise _audience_invalid("registered_from is after registered_to")


async def promocode_is_usable(
    promocode_repository: PromocodeRepository, promocode_id: int
) -> Optional[str]:
    if not await promocode_repository.is_live(promocode_id):
        return None
    promo = await promocode_repository.get_by_id(promocode_id)
    if promo.max_activations is not None:
        if await promocode_repository.get_activations_count(promo.id) >= promo.max_activations:
            return None
    return promo.code


async def assert_references(
    data: SaveBroadcastDto,
    broadcast_repository: "BroadcastRepository",
    promocode_repository: PromocodeRepository,
) -> None:
    if await broadcast_repository.has_missing_references(data.audience):
        raise ValidationError(
            "Audience references a missing plan, ad link or user",
            code=ErrorCode.BROADCAST_AUDIENCE_INVALID,
        )
    if data.promocode_id is not None and not await promocode_is_usable(
        promocode_repository, data.promocode_id
    ):
        raise ValidationError(
            f"Promocode '{data.promocode_id}' is not usable",
            code=ErrorCode.BROADCAST_PROMOCODE_UNUSABLE,
        )
