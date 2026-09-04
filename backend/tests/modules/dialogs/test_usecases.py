import pytest

from app.core.enums import BannerName, ButtonLinkType, DialogFlow, DialogWindowKind, Locale, Role
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import CreateCustomWindowDto, DialogButtonInputDto
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases import (
    CreateCustomDialogWindowUseCase,
    DeleteCustomDialogWindowUseCase,
    GetDialogCatalogUseCase,
    ListDialogWindowsUseCase,
    ResetAllDialogsUseCase,
    ResetDialogWindowUseCase,
    UpdateDialogWindowButtonsUseCase,
    UpdateDialogWindowUseCase,
)
from app.modules.dialogs.usecases.create_custom_window import CreateCustomDialogWindowInput
from app.modules.dialogs.usecases.update_window import UpdateDialogWindowInput
from app.modules.dialogs.usecases.update_window_buttons import UpdateDialogWindowButtonsInput
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="a", name="a", role=Role.OWNER, language=Locale.EN)
USER = UserDto(id=2, name="b", role=Role.USER, language=Locale.EN)

_SNAPSHOT = {
    "banner_name": "menu",
    "buttons": [
        {
            "key": "trial",
            "text_key": "btn-menu.trial",
            "row": 0,
            "column": 0,
            "link_type": "action",
            "action_key": "get_trial",
            "target_window_key": None,
            "url_value": None,
            "visibility_condition": None,
            "style": None,
            "icon_custom_emoji_id": None,
            "is_hidden": False,
        },
    ],
}


@pytest.fixture(autouse=True)
def _catalog():
    catalog._reset_for_tests()
    catalog.register_action("get_trial", lambda: None)
    catalog.register_condition("is_trial_eligible", lambda: None)
    yield
    catalog._reset_for_tests()


async def _seed(repo: DialogRepository) -> None:
    await repo.upsert_seed("menu.main", DialogFlow.MENU, BannerName.MENU, _SNAPSHOT)


async def test_non_admin_denied(dialog_repository: DialogRepository) -> None:
    with pytest.raises(PermissionDeniedError):
        await ListDialogWindowsUseCase(dialog_repository)(USER)


async def test_list_windows_returns_all(dialog_repository: DialogRepository) -> None:
    await _seed(dialog_repository)
    result = await ListDialogWindowsUseCase(dialog_repository)(OWNER)
    assert [w.key for w in result] == ["menu.main"]


async def test_get_catalog_reports_registered_keys(dialog_repository: DialogRepository) -> None:
    await _seed(dialog_repository)
    result = await GetDialogCatalogUseCase(dialog_repository)(OWNER)
    assert result.action_keys == ["get_trial"]
    assert result.condition_keys == ["is_trial_eligible"]
    assert result.navigable_window_keys == ["menu.main"]


async def test_update_window_changes_banner_and_enabled(
    dialog_repository: DialogRepository, uow, redis
) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowUseCase(dialog_repository, uow, redis)
    result = await use_case(OWNER, UpdateDialogWindowInput(key="menu.main", is_enabled=False))
    assert result.is_enabled is False
    assert result.banner_name == BannerName.MENU


async def test_update_buttons_rejects_unknown_action(dialog_repository, uow, redis) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(dialog_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogWindowButtonsInput(
                key="menu.main",
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="btn-menu.x",
                        link_type=ButtonLinkType.ACTION,
                        action_key="not_in_catalog",
                    )
                ],
            ),
        )


async def test_update_buttons_rejects_action_not_belonging_to_this_seed_window(
    dialog_repository, uow, redis
) -> None:
    catalog.register_action("other_action", lambda: None)
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(dialog_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogWindowButtonsInput(
                key="menu.main",
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="btn-menu.x",
                        link_type=ButtonLinkType.ACTION,
                        action_key="other_action",
                    )
                ],
            ),
        )


async def test_update_buttons_rejects_action_on_custom_window(
    dialog_repository, uow, redis
) -> None:
    window = await dialog_repository.create_custom_window("custom.abc", CreateCustomWindowDto())
    use_case = UpdateDialogWindowButtonsUseCase(dialog_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogWindowButtonsInput(
                key=window.key,
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="btn-menu.x",
                        link_type=ButtonLinkType.ACTION,
                        action_key="get_trial",
                    )
                ],
            ),
        )


async def test_update_buttons_rejects_duplicate_position(dialog_repository, uow, redis) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(dialog_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogWindowButtonsInput(
                key="menu.main",
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="a",
                        link_type=ButtonLinkType.ACTION,
                        action_key="get_trial",
                    ),
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="b",
                        link_type=ButtonLinkType.URL,
                        url_value="https://h",
                    ),
                ],
            ),
        )


async def test_update_buttons_rejects_unknown_visibility_condition(
    dialog_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(dialog_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogWindowButtonsInput(
                key="menu.main",
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="a",
                        link_type=ButtonLinkType.ACTION,
                        action_key="get_trial",
                        visibility_condition="not_a_condition",
                    )
                ],
            ),
        )


async def test_update_buttons_rejects_url_without_value(dialog_repository, uow, redis) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(dialog_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogWindowButtonsInput(
                key="menu.main",
                buttons=[
                    DialogButtonInputDto(
                        row=0, column=0, text_key="a", link_type=ButtonLinkType.URL, url_value=""
                    )
                ],
            ),
        )


async def test_update_buttons_rejects_unknown_navigate_target(
    dialog_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(dialog_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogWindowButtonsInput(
                key="menu.main",
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="a",
                        link_type=ButtonLinkType.NAVIGATE,
                        target_window_key="nowhere.win",
                    )
                ],
            ),
        )


async def test_update_buttons_allows_added_url_button(dialog_repository, uow, redis) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(dialog_repository, uow, redis)
    result = await use_case(
        OWNER,
        UpdateDialogWindowButtonsInput(
            key="menu.main",
            buttons=[
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
                    url_value="https://h",
                ),
            ],
        ),
    )
    assert [b.link_type for b in result.buttons] == [ButtonLinkType.ACTION, ButtonLinkType.URL]


async def test_create_custom_window_seeds_translation(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    use_case = CreateCustomDialogWindowUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
    result = await use_case(OWNER, CreateCustomDialogWindowInput(title_text="Hello"))
    assert result.key.startswith("custom.")
    assert result.kind == DialogWindowKind.CUSTOM


async def test_delete_custom_window(dialog_repository, uow, redis) -> None:
    window = await dialog_repository.create_custom_window("custom.del", CreateCustomWindowDto())
    use_case = DeleteCustomDialogWindowUseCase(dialog_repository, uow, redis)
    await use_case(OWNER, window.key)
    with pytest.raises(NotFoundError):
        await dialog_repository.get_by_key_or_raise(window.key)


async def test_reset_window_restores_snapshot(dialog_repository, uow, redis) -> None:
    await _seed(dialog_repository)
    await dialog_repository.replace_buttons("menu.main", [])
    result = await ResetDialogWindowUseCase(dialog_repository, uow, redis)(OWNER, "menu.main")
    assert [b.text_key for b in result.buttons] == ["btn-menu.trial"]


async def test_reset_all_restores_every_seed_window(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    await dialog_repository.replace_buttons("menu.main", [])
    use_case = ResetAllDialogsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
    await use_case(OWNER, None)
    window = await dialog_repository.get_by_key_or_raise("menu.main")
    assert [b.text_key for b in window.buttons] == ["btn-menu.trial"]
