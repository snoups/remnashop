from typing import Optional

import pytest

from app.core.db.uow import UnitOfWork
from app.modules.settings.dto import UpdateBotSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import GetCabinetSettingsUseCase
from app.modules.users.dto import UserDto

_USER = UserDto(id=1, name="user")


@pytest.fixture
def use_case(settings_repository: SettingsRepository, uow: UnitOfWork) -> GetCabinetSettingsUseCase:
    return GetCabinetSettingsUseCase(settings_repository, uow)


async def _configure_bot(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_bot_settings(
            UpdateBotSettingsDto(token="123:abc", secret_token="s")
        )


def _patch_username(monkeypatch: pytest.MonkeyPatch, username: Optional[str]) -> None:
    async def _username(token: str, proxy: object) -> Optional[str]:
        return username

    monkeypatch.setattr(
        "app.modules.settings.usecases.get_cabinet_settings.fetch_bot_username", _username
    )


async def test_cabinet_settings_without_a_bot(use_case: GetCabinetSettingsUseCase) -> None:
    result = await use_case(_USER)
    assert result.max_active_subscriptions == 3
    assert result.bot_username is None
    assert result.device_single_reset_enabled is True
    assert result.device_all_reset_enabled is True
    assert result.link_reset_enabled is True


async def test_cabinet_settings_reports_the_bot_username(
    use_case: GetCabinetSettingsUseCase,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _configure_bot(settings_repository, uow)
    _patch_username(monkeypatch, "shop_bot")
    assert (await use_case(_USER)).bot_username == "shop_bot"


async def test_cabinet_settings_survive_an_unreachable_bot(
    use_case: GetCabinetSettingsUseCase,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _configure_bot(settings_repository, uow)
    _patch_username(monkeypatch, None)
    assert (await use_case(_USER)).bot_username is None
