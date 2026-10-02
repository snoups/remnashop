import pytest

from app.core.bot_signals import RedisBotSignals
from app.core.enums import ButtonLinkType, DialogFlow, DialogWindowKind, Locale, Role
from app.core.exceptions import ValidationError
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import (
    CreateCustomWindowDto,
    DialogButtonInputDto,
    DialogExportDto,
    DialogTextExportDto,
    DialogWindowExportDto,
)
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.usecases import ExportDialogsUseCase, ImportDialogsUseCase
from app.modules.dialogs.usecases.export_dialogs import EXPORT_VERSION
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="a", name="a", role=Role.OWNER, language=Locale.EN)

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
        }
    ],
}


@pytest.fixture(autouse=True)
def _catalog():
    catalog._reset_for_tests()
    catalog.register_action_key("get_trial")
    catalog.register_window(
        catalog.CatalogWindow(
            key="menu.main",
            flow=DialogFlow.MENU,
            text_keys=("msg-main-menu",),
            banner_name="menu",
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
    yield
    catalog._reset_for_tests()


async def _export(dialog_repository, translation_repository, settings_repository, uow):
    return await ExportDialogsUseCase(dialog_repository, translation_repository, uow)(OWNER)


async def test_export_carries_windows_and_their_texts(
    dialog_repository: DialogRepository, translation_repository, settings_repository, uow
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, "menu", _SNAPSHOT)
    if Locale.EN not in await translation_repository.list_active_locales():
        await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.seed_missing(Locale.EN, "btn-menu", "trial", "Try for free")
    # Not a dialog key: must stay out of the file, since import writes back what it finds.
    await translation_repository.seed_missing(Locale.EN, "cmd-start", "", "Start")

    export = await _export(dialog_repository, translation_repository, settings_repository, uow)

    assert export.version == EXPORT_VERSION
    assert [w.key for w in export.windows] == ["menu.main"]
    assert [b.text_key for b in export.windows[0].buttons] == ["btn-menu.trial"]
    assert ("btn-menu", "trial") in {(t.message_id, t.attribute_id) for t in export.texts}
    assert "cmd-start" not in {t.message_id for t in export.texts}


async def test_import_restores_an_exported_configuration(
    dialog_repository: DialogRepository, translation_repository, settings_repository, uow, redis
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, "menu", _SNAPSHOT)
    if Locale.EN not in await translation_repository.list_active_locales():
        await translation_repository.add_active_locale(Locale.EN)
    await translation_repository.seed_missing(Locale.EN, "btn-menu", "trial", "Try for free")

    export = await _export(dialog_repository, translation_repository, settings_repository, uow)

    # Drift away from the exported state, then import it back.
    await dialog_repository.replace_buttons("menu.main", [])
    await translation_repository.update_value(Locale.EN, "btn-menu", "trial", "Changed")

    await ImportDialogsUseCase(
        dialog_repository, translation_repository, uow, RedisBotSignals(redis)
    )(OWNER, export)

    restored = await dialog_repository.get_by_key_or_raise("menu.main")
    assert [b.text_key for b in restored.buttons] == ["btn-menu.trial"]
    label = await translation_repository.get(Locale.EN, "btn-menu", "trial")
    assert label is not None
    assert label.value == "Try for free"


async def test_import_deletes_custom_windows_missing_from_the_file(
    dialog_repository: DialogRepository, translation_repository, settings_repository, uow, redis
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, "menu", _SNAPSHOT)
    export = await _export(dialog_repository, translation_repository, settings_repository, uow)
    await dialog_repository.create_custom_window("custom.later", CreateCustomWindowDto())

    await ImportDialogsUseCase(
        dialog_repository, translation_repository, uow, RedisBotSignals(redis)
    )(OWNER, export)

    assert await dialog_repository.get_by_key("custom.later") is None


async def test_import_creates_a_custom_window_from_the_file(
    dialog_repository: DialogRepository, translation_repository, settings_repository, uow, redis
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, "menu", _SNAPSHOT)
    if Locale.EN not in await translation_repository.list_active_locales():
        await translation_repository.add_active_locale(Locale.EN)

    payload = DialogExportDto(
        version=EXPORT_VERSION,
        windows=[
            DialogWindowExportDto(
                key="custom-faq",
                kind=DialogWindowKind.CUSTOM,
                banner_name=None,
                is_enabled=True,
                position=0,
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="msg-dialog-custom-back",
                        link_type=ButtonLinkType.NAVIGATE,
                        target_window_key="menu.main",
                    )
                ],
            )
        ],
        texts=[
            DialogTextExportDto(
                locale=Locale.EN, message_id="msg-dialog-custom-faq", attribute_id="", value="FAQ"
            )
        ],
    )

    await ImportDialogsUseCase(
        dialog_repository, translation_repository, uow, RedisBotSignals(redis)
    )(OWNER, payload)

    created = await dialog_repository.get_by_key("custom-faq")
    assert created is not None
    assert created.slot is not None
    assert [b.target_window_key for b in created.buttons] == ["menu.main"]
    body = await translation_repository.get(Locale.EN, "msg-dialog-custom-faq", "")
    assert body is not None
    assert body.value == "FAQ"


async def test_import_rejects_a_button_pointing_nowhere(
    dialog_repository: DialogRepository, translation_repository, settings_repository, uow, redis
) -> None:
    await dialog_repository.upsert_seed("menu.main", DialogFlow.MENU, "menu", _SNAPSHOT)
    payload = DialogExportDto(
        version=EXPORT_VERSION,
        windows=[
            DialogWindowExportDto(
                key="menu.main",
                kind=DialogWindowKind.SEED,
                banner_name="menu",
                is_enabled=True,
                position=0,
                buttons=[
                    DialogButtonInputDto(
                        row=0,
                        column=0,
                        text_key="btn-menu.trial",
                        link_type=ButtonLinkType.NAVIGATE,
                        target_window_key="menu.nowhere",
                    )
                ],
            )
        ],
        texts=[],
    )

    with pytest.raises(ValidationError):
        await ImportDialogsUseCase(
            dialog_repository, translation_repository, uow, RedisBotSignals(redis)
        )(OWNER, payload)


async def test_import_rejects_an_unknown_version(
    dialog_repository: DialogRepository, translation_repository, settings_repository, uow, redis
) -> None:
    with pytest.raises(ValidationError):
        await ImportDialogsUseCase(
            dialog_repository, translation_repository, uow, RedisBotSignals(redis)
        )(OWNER, DialogExportDto(version=99, windows=[], texts=[]))
