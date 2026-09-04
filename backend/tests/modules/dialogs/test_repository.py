import pytest

from app.core.enums import BannerName, ButtonLinkType, DialogFlow
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.dialogs.dto import (
    CreateCustomWindowDto,
    DialogButtonInputDto,
    UpdateDialogWindowDto,
)
from app.modules.dialogs.repository import DialogRepository

_SNAPSHOT = {
    "banner_name": "menu",
    "buttons": [
        {
            "key": "sub",
            "text_key": "btn-menu.subscription",
            "row": 0,
            "column": 0,
            "link_type": "navigate",
            "action_key": None,
            "target_window_key": "subscription.main",
            "url_value": None,
            "visibility_condition": None,
            "style": None,
            "icon_custom_emoji_id": None,
            "is_hidden": False,
        }
    ],
}


async def test_upsert_seed_creates_once(dialog_repository: DialogRepository) -> None:
    created = await dialog_repository.upsert_seed(
        "menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT
    )
    assert created is True
    again = await dialog_repository.upsert_seed(
        "menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT
    )
    assert again is False

    window = await dialog_repository.get_by_key_or_raise("menu.main")
    assert window.banner_name == BannerName.MENU
    assert len(window.buttons) == 1
    assert window.buttons[0].link_type == ButtonLinkType.NAVIGATE


async def test_replace_buttons_swaps_layout(dialog_repository: DialogRepository) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    updated = await dialog_repository.replace_buttons(
        "menu.main",
        [
            DialogButtonInputDto(
                row=0,
                column=0,
                text_key="btn-menu.trial",
                link_type=ButtonLinkType.ACTION,
                action_key="get_trial",
            ),
            DialogButtonInputDto(
                row=1,
                column=0,
                text_key="btn-menu.help",
                link_type=ButtonLinkType.URL,
                url_value="https://help",
            ),
        ],
    )
    assert [b.text_key for b in updated.buttons] == ["btn-menu.trial", "btn-menu.help"]


async def test_reset_restores_snapshot(dialog_repository: DialogRepository) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    await dialog_repository.update_window(
        "menu.main", UpdateDialogWindowDto(banner_name=BannerName.DEFAULT)
    )
    await dialog_repository.replace_buttons("menu.main", [])

    reset = await dialog_repository.reset_to_snapshot("menu.main")
    assert reset.banner_name == BannerName.MENU
    assert [b.text_key for b in reset.buttons] == ["btn-menu.subscription"]


async def test_create_custom_window_conflict(dialog_repository: DialogRepository) -> None:
    await dialog_repository.create_custom_window("custom.faq", CreateCustomWindowDto())
    with pytest.raises(ConflictError):
        await dialog_repository.create_custom_window("custom.faq", CreateCustomWindowDto())


async def test_delete_rejects_seed_window(dialog_repository: DialogRepository) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)
    with pytest.raises(ValidationError):
        await dialog_repository.delete_custom_window("menu.main")


async def test_reset_rejects_custom_window(dialog_repository: DialogRepository) -> None:
    await dialog_repository.create_custom_window("custom.faq", CreateCustomWindowDto())
    with pytest.raises(ValidationError):
        await dialog_repository.reset_to_snapshot("custom.faq")


async def test_get_by_key_or_raise_missing(dialog_repository: DialogRepository) -> None:
    with pytest.raises(NotFoundError):
        await dialog_repository.get_by_key_or_raise("nope")
