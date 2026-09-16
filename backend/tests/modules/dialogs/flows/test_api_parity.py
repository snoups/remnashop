import subprocess
import sys
from pathlib import Path

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import ButtonLinkType, DialogWindowKind, Locale, Role
from app.modules.dialogs import catalog
from app.modules.dialogs.dto import DialogButtonInputDto
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.seed import ensure_dialogs_seeded
from app.modules.dialogs.usecases import GetDialogCatalogUseCase, UpdateDialogWindowButtonsUseCase
from app.modules.dialogs.usecases.update_window_buttons import UpdateDialogWindowButtonsInput
from app.modules.users.dto import UserDto

# Same construction tests/modules/dialogs/test_usecases.py uses for its OWNER actor --
# not a fixture, a plain module-level constant, matched here for consistency.
OWNER = UserDto(id=1, login="a", name="a", role=Role.OWNER, language=Locale.EN)


@pytest.fixture(autouse=True)
def _clean():
    catalog._reset_for_tests()
    yield
    catalog._reset_for_tests()


def test_flows_package_imports_without_aiogram() -> None:
    # A subprocess, not an in-process sys.modules diff: this file's own module-level
    # `from app.modules.dialogs import catalog` import already pulls in
    # app.modules.dialogs.flows (transitively) before any test body runs, which made
    # an in-process "newly imported" check vacuously pass regardless of what the code
    # under test actually does. A cold subprocess has no such contamination.
    code = (
        "import sys\n"
        "sys.modules['aiogram'] = None\n"
        "sys.modules['aiogram_dialog'] = None\n"
        "from app.modules.dialogs.flows import register_all_flow_metadata\n"
        "register_all_flow_metadata()\n"
        "leaked = [m for m in sys.modules if m.startswith('app.telegram')]\n"
        "assert not leaked, f'app.telegram modules leaked: {leaked}'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=Path(__file__).parents[4]
    )
    assert result.returncode == 0, result.stderr


async def test_get_catalog_usecase_sees_full_catalog_from_metadata_alone(
    dialog_repository: DialogRepository,
    translations_repository,
    settings_repository,
    uow: UnitOfWork,
) -> None:
    from app.modules.dialogs import register_all_flow_metadata  # noqa: PLC0415

    register_all_flow_metadata()
    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)

    result = await GetDialogCatalogUseCase(dialog_repository, uow)(OWNER, None)

    assert {
        "get_trial",
        "delete_device",
        "delete_all_devices",
        "reissue_subscription",
    } <= set(result.action_keys)
    assert {
        "trial_available",
        "has_device_limit",
        "connectable",
        "has_devices",
    } <= set(result.condition_keys)
    assert "subscription.url" in result.variable_keys
    assert "menu.main" in result.seed_window_keys


async def test_update_buttons_accepts_a_real_action_from_metadata_alone(
    dialog_repository: DialogRepository, translations_repository, settings_repository, uow, redis
) -> None:
    from app.modules.dialogs import register_all_flow_metadata  # noqa: PLC0415

    register_all_flow_metadata()
    # UpdateDialogWindowButtonsUseCase reads the window from the database, not the
    # in-process catalog -- it has to actually exist as a row first.
    await ensure_dialogs_seeded(dialog_repository, translations_repository, settings_repository)
    window = await dialog_repository.get_by_key_or_raise("menu.main")
    assert window.kind == DialogWindowKind.SEED

    use_case = UpdateDialogWindowButtonsUseCase(
        dialog_repository, translations_repository, settings_repository, uow, redis
    )
    # This is the exact round trip the telegram-render-engine review found broken:
    # read a seed window's own action key back through the admin API's write path.
    updated = await use_case(
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
                )
            ],
        ),
    )
    assert updated.buttons[0].action_key == "get_trial"
