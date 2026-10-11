from app.core.db.uow import UnitOfWork
from app.core.enums import SmtpSecurity
from app.modules.settings.dto import UpdateEmailSettingsDto
from app.modules.settings.repository import SettingsRepository


async def test_email_settings_default_and_update(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    async with uow:
        empty = await settings_repository.get_email_settings()
        assert not empty.is_configured

        updated = await settings_repository.update_email_settings(
            UpdateEmailSettingsDto(
                host="smtp.example.com",
                port=465,
                security=SmtpSecurity.TLS,
                username="shop",
                password="pw",
                from_address="no-reply@example.com",
            )
        )
    assert updated.is_configured
    assert updated.is_password_set
    assert updated.password is not None and updated.password.get_secret_value() == "pw"


async def test_password_is_not_cleared_by_omitted_field(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await settings_repository.update_email_settings(UpdateEmailSettingsDto(password="pw"))
        after = await settings_repository.update_email_settings(UpdateEmailSettingsDto(port=25))
    assert after.password is not None and after.password.get_secret_value() == "pw"
