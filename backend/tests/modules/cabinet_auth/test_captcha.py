import httpx
import pytest

from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import CaptchaProvider
from app.core.error_codes import ErrorCode
from app.modules.cabinet_auth import captcha
from app.modules.settings.dto import UpdateCabinetAuthSettingsDto, UpdateEmailSettingsDto
from app.modules.settings.repository import SettingsRepository
from tests.fakes.dispatch import RecordingDispatch

_CODE_URL = f"{API_V1}/auth/email/code"


@pytest.fixture(autouse=True)
async def _captcha_on(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_cabinet_auth_settings(
            UpdateCabinetAuthSettingsDto(
                email_enabled=True,
                captcha_enabled=True,
                captcha_provider=CaptchaProvider.HCAPTCHA,
                captcha_site_key="site",
                captcha_secret_key="secret",
            )
        )
        await settings_repository.update_email_settings(
            UpdateEmailSettingsDto(host="smtp.example.com", from_address="shop@example.com")
        )


@pytest.fixture
def siteverify(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, str]]]:
    calls: list[tuple[str, dict[str, str]]] = []

    async def fake(url: str, form: dict[str, str]) -> bool:
        calls.append((url, form))
        if form["response"] == "down":
            raise httpx.ConnectTimeout("down")
        return form["response"] == "good"

    monkeypatch.setattr(captcha, "_siteverify", fake)
    return calls


@pytest.mark.parametrize("token", [None, "bad", "down"])
async def test_code_is_not_sent_without_a_passed_captcha(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    siteverify: list[tuple[str, dict[str, str]]],
    token: str,
) -> None:
    response = await client.post(_CODE_URL, json={"email": "a@mail.ru", "captcha_token": token})

    assert response.status_code == 403
    assert response.json()["code"] == ErrorCode.CAPTCHA_FAILED
    assert email_dispatch.messages == []


async def test_code_is_sent_after_the_provider_confirms(
    client: httpx.AsyncClient,
    email_dispatch: RecordingDispatch,
    siteverify: list[tuple[str, dict[str, str]]],
) -> None:
    response = await client.post(_CODE_URL, json={"email": "a@mail.ru", "captcha_token": "good"})

    assert response.status_code == 204
    assert len(email_dispatch.messages) == 1
    url, form = siteverify[0]
    assert url == "https://api.hcaptcha.com/siteverify"
    assert form["secret"] == "secret"


async def test_methods_hand_the_widget_its_public_key_only(client: httpx.AsyncClient) -> None:
    methods = (await client.get(f"{API_V1}/auth/methods")).json()

    assert methods["captcha"] == {"provider": "HCAPTCHA", "site_key": "site"}
