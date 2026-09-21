import pytest
from fluent_compiler.bundle import FluentBundle

from app.core.db.uow import UnitOfWork
from app.core.enums import ButtonLinkType, DialogFlow, DialogWindowKind, Locale, Role
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
from app.modules.dialogs.usecases.update_text import UpdateDialogTextInput, UpdateDialogTextUseCase
from app.modules.dialogs.usecases.update_window import UpdateDialogWindowInput
from app.modules.dialogs.usecases.update_window_buttons import UpdateDialogWindowButtonsInput
from app.modules.translations import serialize_to_fluent
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
            "is_hidden": False,
        },
    ],
}


@pytest.fixture(autouse=True)
def _catalog():
    catalog._reset_for_tests()
    catalog.register_action_key("get_trial")
    catalog.bind_action_handler("get_trial", lambda: None)
    catalog.register_condition("is_trial_eligible", lambda: None)
    yield
    catalog._reset_for_tests()


async def _seed(repo: DialogRepository) -> None:
    await repo.upsert_seed("menu.main", DialogFlow.MENU, "menu", _SNAPSHOT)


async def test_non_admin_denied(
    dialog_repository: DialogRepository,
    uow: UnitOfWork,
) -> None:
    with pytest.raises(PermissionDeniedError):
        await ListDialogWindowsUseCase(dialog_repository, uow)(USER)


async def test_list_windows_returns_all(
    dialog_repository: DialogRepository,
    uow: UnitOfWork,
) -> None:
    await _seed(dialog_repository)
    result = await ListDialogWindowsUseCase(dialog_repository, uow)(OWNER)
    assert [w.key for w in result] == ["menu.main"]


async def test_get_catalog_reports_registered_keys(
    dialog_repository: DialogRepository,
    uow: UnitOfWork,
) -> None:
    await _seed(dialog_repository)
    result = await GetDialogCatalogUseCase(dialog_repository, uow)(OWNER)
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
    assert result.banner_name == "menu"


async def test_update_buttons_rejects_unknown_action(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
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
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    catalog.register_action_key("other_action")
    catalog.bind_action_handler("other_action", lambda: None)
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
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
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    window = await dialog_repository.create_custom_window("custom.abc", CreateCustomWindowDto())
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
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


async def test_update_buttons_rejects_duplicate_position(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
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
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
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


async def test_update_buttons_rejects_url_without_value(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
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
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
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


async def test_update_buttons_allows_added_url_button(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    _register_button_window("btn-menu.trial", "btn-menu.help")
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
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


@pytest.mark.parametrize(
    "url_value",
    [
        "example.com",  # no scheme -- Telegram refuses the whole keyboard over it
        "javascript:alert(1)",
        "${made_up_variable}",
    ],
)
async def test_update_buttons_rejects_unusable_url(
    url_value, dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogWindowButtonsInput(
                key="menu.main",
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="btn-menu.help",
                        link_type=ButtonLinkType.URL,
                        url_value=url_value,
                    )
                ],
            ),
        )


async def test_update_buttons_accepts_url_built_from_a_catalog_variable(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    catalog.register_variable("subscription.url", lambda data: data.get("connect_url", ""))
    _register_button_window("btn-menu.connect")
    await _seed(dialog_repository)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
    result = await use_case(
        OWNER,
        UpdateDialogWindowButtonsInput(
            key="menu.main",
            buttons=[
                DialogButtonInputDto(
                    row=0,
                    column=0,
                    text_key="btn-menu.connect",
                    link_type=ButtonLinkType.URL,
                    url_value="${subscription.url}",
                )
            ],
        ),
    )
    assert result.buttons[0].url_value == "${subscription.url}"


async def test_create_custom_window_seeds_translation(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    use_case = CreateCustomDialogWindowUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
    result = await use_case(OWNER, CreateCustomDialogWindowInput(title_text="Hello"))
    assert result.key.startswith("custom-")
    assert result.kind == DialogWindowKind.CUSTOM


async def test_delete_custom_window(
    dialog_repository, banner_repository, config, uow, redis
) -> None:
    window = await dialog_repository.create_custom_window("custom.del", CreateCustomWindowDto())
    use_case = DeleteCustomDialogWindowUseCase(
        dialog_repository, banner_repository, config, uow, redis
    )
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


async def test_reset_all_restores_an_edited_button_label(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    # The label lives in the "trial" attribute of "btn-menu"; a reset that looked
    # for a message called "btn-menu.trial" silently found nothing and left the
    # edit in place.
    await _seed(dialog_repository)
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.main",
            flow=DialogFlow.MENU,
            text_keys=(),
            banner_name=None,
            buttons=(
                catalog.CatalogButton(
                    key="trial",
                    text_key="btn-menu.trial",
                    link_type=ButtonLinkType.ACTION,
                    action_key="get_trial",
                ),
            ),
        )
    )
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "btn-menu", "trial", "Try for free")
    await translations_repository.update_value(Locale.EN, "btn-menu", "trial", "Edited")

    use_case = ResetAllDialogsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
    await use_case(OWNER, None)

    restored = await translations_repository.get(Locale.EN, "btn-menu", "trial")
    assert restored is not None
    assert restored.value == "Try for free"


async def test_update_dialog_text_rejects_a_dotted_message_id(
    dialog_repository: DialogRepository,
    translations_repository,
    settings_repository,
    uow,
    redis,
) -> None:
    use_case = UpdateDialogTextUseCase(translations_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogTextInput(
                locale=Locale.EN,
                message_id="btn-menu.trial",
                attribute_id="",
                value="Anything",
            ),
        )


def _register_button_window(*text_keys: str) -> None:
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.main",
            flow=DialogFlow.MENU,
            text_keys=(),
            banner_name=None,
            buttons=tuple(
                catalog.CatalogButton(
                    key=f"b{index}",
                    text_key=text_key,
                    link_type=ButtonLinkType.URL,
                )
                for index, text_key in enumerate(text_keys)
            ),
        )
    )


def _register_text_window(*text_keys: str) -> None:
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.text_window",
            flow=DialogFlow.MENU,
            text_keys=text_keys,
            banner_name=None,
        )
    )


async def test_update_dialog_text_allows_known_variable(
    dialog_repository: DialogRepository,
    translations_repository,
    settings_repository,
    uow,
    redis,
) -> None:
    catalog.register_variable("name", lambda data: data.get("name", ""))
    _register_text_window("msg-window-greeting")
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "msg-window-greeting", "", "Hi!")

    use_case = UpdateDialogTextUseCase(translations_repository, uow, redis)
    updated = await use_case(
        OWNER,
        UpdateDialogTextInput(
            locale=Locale.EN,
            message_id="msg-window-greeting",
            attribute_id="",
            value="Hi, { $name }!",
        ),
    )
    assert updated.value == "Hi, { $name }!"


async def test_update_dialog_text_edits_attribute_keyed_button_label(
    dialog_repository: DialogRepository,
    translations_repository,
    settings_repository,
    uow,
    redis,
) -> None:
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.main",
            flow=DialogFlow.MENU,
            text_keys=("msg-main-menu",),
            banner_name="menu",
            buttons=(
                catalog.CatalogButton(
                    key="subscription",
                    text_key="btn-menu.subscription",
                    link_type=ButtonLinkType.NAVIGATE,
                    target_window_key="menu.main",
                ),
            ),
        )
    )
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "btn-menu", "subscription", "Sub")

    use_case = UpdateDialogTextUseCase(translations_repository, uow, redis)
    updated = await use_case(
        OWNER,
        UpdateDialogTextInput(
            locale=Locale.EN,
            message_id="btn-menu",
            attribute_id="subscription",
            value="Subscription",
        ),
    )
    assert updated.value == "Subscription"
    assert updated.attribute_id == "subscription"


async def test_update_dialog_text_rejects_non_dialog_message_id(
    dialog_repository: DialogRepository,
    translations_repository,
    settings_repository,
    uow,
    redis,
) -> None:
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "command", "menu", "Menu")

    use_case = UpdateDialogTextUseCase(translations_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogTextInput(
                locale=Locale.EN, message_id="command", attribute_id="menu", value="Open menu"
            ),
        )


async def test_update_dialog_text_rejects_unknown_variable(
    dialog_repository: DialogRepository,
    translations_repository,
    settings_repository,
    uow,
    redis,
) -> None:
    _register_text_window("msg-window-greeting2")
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "msg-window-greeting2", "", "Hi!")

    use_case = UpdateDialogTextUseCase(translations_repository, uow, redis)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogTextInput(
                locale=Locale.EN,
                message_id="msg-window-greeting2",
                attribute_id="",
                value="Hi, { $made_up }!",
            ),
        )


async def test_update_dialog_text_keeps_multiline_value(
    dialog_repository: DialogRepository,
    translations_repository,
    settings_repository,
    uow,
    redis,
) -> None:
    # A window body is a Telegram message, so paragraphs are the normal case --
    # and it has to survive the Fluent round-trip, not just the write.
    _register_text_window("msg-window-greeting3")
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    await translations_repository.seed_missing(Locale.EN, "msg-window-greeting3", "", "Hi!")

    use_case = UpdateDialogTextUseCase(translations_repository, uow, redis)
    updated = await use_case(
        OWNER,
        UpdateDialogTextInput(
            locale=Locale.EN,
            message_id="msg-window-greeting3",
            attribute_id="",
            value="Hi there\n\nSecond paragraph",
        ),
    )

    assert updated.value == "Hi there\n\nSecond paragraph"

    entries = await translations_repository.list_by_locale(Locale.EN)
    bundle = FluentBundle.from_string(Locale.EN.value, text=serialize_to_fluent(entries))
    assert bundle.check_messages() == []
    value, errors = bundle.format("msg-window-greeting3", {})
    assert (value, errors) == ("Hi there\n\nSecond paragraph", [])


async def test_update_buttons_seeds_translation_for_new_custom_text_key(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    await _seed(dialog_repository)
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    _register_button_window("btn-menu.trial")
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
    new_key = f"{catalog.CUSTOM_TEXT_KEY_PREFIX}abc123"
    await use_case(
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
                    text_key=new_key,
                    link_type=ButtonLinkType.URL,
                    url_value="https://h",
                ),
            ],
        ),
    )
    entries = await translations_repository.list_by_locale(Locale.EN)
    assert any(e.message_id == new_key and e.value == "" for e in entries)


async def test_update_buttons_rejects_a_text_key_no_window_owns(
    dialog_repository, translations_repository, settings_repository, uow, redis
) -> None:
    # The key an admin sends is what authorizes a write into bot_translations, so
    # one that belongs to no catalog button and is outside the custom namespace
    # is refused instead of quietly not being seeded.
    await _seed(dialog_repository)
    if Locale.EN not in await settings_repository.list_active_locales():
        await settings_repository.add_active_locale(Locale.EN)
    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateDialogWindowButtonsInput(
                key="menu.main",
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="btn-menu.freeform",
                        link_type=ButtonLinkType.URL,
                        url_value="https://h",
                    ),
                ],
            ),
        )
    entries = await translations_repository.list_by_locale(Locale.EN)
    assert not any(e.message_id == "btn-menu.freeform" for e in entries)
