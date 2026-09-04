import pytest

from app.core.enums import (
    AddOnType,
    ButtonLinkType,
    ButtonStyleKind,
    Currency,
    DialogFlow,
    DialogWindowKind,
    OAuthProvider,
    PlanAvailability,
    PlanType,
    SubscriptionStatus,
)


@pytest.mark.parametrize("value", ["github", "GITHUB", "Github"])
def test_oauth_provider_accepts_any_case(value: str) -> None:
    assert OAuthProvider(value) is OAuthProvider.GITHUB


def test_oauth_provider_keeps_uppercase_value() -> None:
    # The Postgres enum labels are 'GITHUB'/'TELEGRAM' -- only construction is
    # case-insensitive, the stored value must not drift.
    assert OAuthProvider.GITHUB.value == "GITHUB"
    assert OAuthProvider.TELEGRAM.value == "TELEGRAM"


def test_oauth_provider_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        OAuthProvider("nope")


def test_plan_type_members() -> None:
    assert {member.value for member in PlanType} == {"TRAFFIC", "DEVICES", "BOTH", "UNLIMITED"}


def test_plan_availability_members() -> None:
    assert {member.value for member in PlanAvailability} == {
        "ALL",
        "NEW",
        "EXISTING",
        "INVITED",
        "ALLOWED",
        "LINK",
    }


def test_currency_symbols() -> None:
    assert Currency.USD.symbol == "$"
    assert Currency.XTR.symbol == "★"
    assert Currency.RUB.symbol == "₽"


def test_subscription_status_members() -> None:
    assert {member.value for member in SubscriptionStatus} == {
        "ACTIVE",
        "LIMITED",
        "EXPIRED",
        "DISABLED",
        "DELETED",
    }


def test_addon_type_members() -> None:
    assert {member.value for member in AddOnType} == {"TRAFFIC", "DEVICES"}


def test_dialog_enum_values_are_lowercase_names() -> None:
    assert DialogWindowKind.SEED.value == "seed"
    assert DialogFlow.SUBSCRIPTION.value == "subscription"
    assert ButtonLinkType.NAVIGATE.value == "navigate"
    assert ButtonStyleKind.DANGER.value == "danger"


def test_button_style_kind_matches_telegram_style_names() -> None:
    # aiogram InlineKeyboardButton.style accepts exactly these strings
    assert {s.value for s in ButtonStyleKind} == {"primary", "success", "danger"}
