from app.core.db.uow import UnitOfWork
from app.core.enums import SmtpSecurity
from app.modules.settings.dto import EmailSettingsDto, UpdateEmailSettingsDto
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


def test_profile_falls_back_to_primary() -> None:
    settings = EmailSettingsDto(
        host="smtp.a", from_address="a@x", rate_per_minute=30, bulk_rate_per_minute=60
    )
    profile = settings.profile(bulk=True)
    assert profile.host == "smtp.a" and not profile.is_bulk
    assert profile.rate_per_minute == 30


def test_profile_uses_bulk_when_configured() -> None:
    settings = EmailSettingsDto(
        host="smtp.a",
        from_address="a@x",
        bulk_host="smtp.b",
        bulk_from_address="news@x",
        bulk_port=2525,
        rate_per_minute=30,
        bulk_rate_per_minute=90,
    )
    profile = settings.profile(bulk=True)
    assert (
        profile.host,
        profile.port,
        profile.from_address,
        profile.rate_per_minute,
        profile.is_bulk,
    ) == ("smtp.b", 2525, "news@x", 90, True)


async def test_reset_bulk_keeps_primary_and_rate(
    settings_repository: SettingsRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await settings_repository.update_email_settings(
            UpdateEmailSettingsDto(
                host="smtp.a",
                from_address="a@x",
                bulk_host="smtp.b",
                bulk_password="p",
                bulk_rate_per_minute=120,
            )
        )
        reset = await settings_repository.reset_bulk_email_settings()
    assert reset.host == "smtp.a"
    assert reset.bulk_host is None and reset.bulk_password is None
    assert reset.bulk_rate_per_minute == 120
