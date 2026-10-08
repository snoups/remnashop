from typing import Optional

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import AccessDenial, AccessMode, AdLinkChannel
from app.modules.access.dto import CheckRegistrationAccessDto
from app.modules.access.usecases import CheckRegistrationAccessUseCase
from app.modules.advertising.dto import CreateAdLinkDto, UpdateAdLinkDto
from app.modules.advertising.repository import AdLinkRepository
from app.modules.settings.dto import UpdateAccessSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.settings.usecases import GetAccessSettingsUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
def use_case(
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
) -> CheckRegistrationAccessUseCase:
    return CheckRegistrationAccessUseCase(
        GetAccessSettingsUseCase(settings_repository, uow), user_repository, ad_link_repository, uow
    )


async def _set(settings_repository: SettingsRepository, uow: UnitOfWork, **values: object) -> None:
    async with uow:
        await settings_repository.update_access_settings(UpdateAccessSettingsDto(**values))  # type: ignore[arg-type]


async def _check(
    use_case: CheckRegistrationAccessUseCase,
    *,
    telegram_id: Optional[int] = 555_001,
    referral_code: Optional[str] = None,
    ad_link_code: Optional[str] = None,
    channel: AdLinkChannel = AdLinkChannel.BOT,
) -> Optional[AccessDenial]:
    return await use_case.system(
        CheckRegistrationAccessDto(
            channel=channel,
            telegram_id=telegram_id,
            referral_code=referral_code,
            ad_link_code=ad_link_code,
        )
    )


async def test_open_shop_lets_anyone_in(use_case: CheckRegistrationAccessUseCase) -> None:
    assert await _check(use_case) is None


async def test_existing_user_passes_in_every_mode(
    use_case: CheckRegistrationAccessUseCase,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    await user_repository.create(CreateUserDto(name="old", telegram_id=555_002))
    for mode in AccessMode:
        await _set(settings_repository, uow, mode=mode, registration_enabled=False)
        assert await _check(use_case, telegram_id=555_002) is None


@pytest.mark.parametrize(
    ("mode", "registration_enabled", "expected"),
    [
        (AccessMode.RESTRICTED, True, AccessDenial.RESTRICTED),
        (AccessMode.RESTRICTED, False, AccessDenial.RESTRICTED),
        (AccessMode.PUBLIC, False, AccessDenial.REGISTRATION_DISABLED),
        (AccessMode.INVITED, False, AccessDenial.REGISTRATION_DISABLED),
        (AccessMode.INVITED, True, AccessDenial.INVITE_ONLY),
    ],
)
async def test_new_user_denials(
    use_case: CheckRegistrationAccessUseCase,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
    mode: AccessMode,
    registration_enabled: bool,
    expected: AccessDenial,
) -> None:
    await _set(settings_repository, uow, mode=mode, registration_enabled=registration_enabled)
    assert await _check(use_case) is expected


async def test_invited_mode_accepts_a_live_referral_code(
    use_case: CheckRegistrationAccessUseCase,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    referrer = await user_repository.create(CreateUserDto(name="ref", telegram_id=555_003))
    await _set(settings_repository, uow, mode=AccessMode.INVITED)

    assert await _check(use_case, referral_code=referrer.referral_code) is None
    assert await _check(use_case, referral_code="nope") is AccessDenial.INVITE_ONLY


async def test_invited_mode_rejects_a_blocked_referrer(
    use_case: CheckRegistrationAccessUseCase,
    settings_repository: SettingsRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    referrer = await user_repository.create(CreateUserDto(name="ref", telegram_id=555_004))
    async with uow:
        await user_repository.set_blocked(referrer.id, True)
    await _set(settings_repository, uow, mode=AccessMode.INVITED)

    assert await _check(use_case, referral_code=referrer.referral_code) is AccessDenial.INVITE_ONLY


async def test_invited_mode_ad_link_must_be_active_and_allow_the_channel(
    use_case: CheckRegistrationAccessUseCase,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await ad_link_repository.create(
            CreateAdLinkDto(name="web only", code="webonly", allow_bot=False)
        )
        await ad_link_repository.create(CreateAdLinkDto(name="bot", code="botlink"))
    await _set(settings_repository, uow, mode=AccessMode.INVITED)

    assert await _check(use_case, ad_link_code="botlink") is None
    assert await _check(use_case, ad_link_code="webonly") is AccessDenial.INVITE_ONLY
    assert await _check(use_case, ad_link_code="missing") is AccessDenial.INVITE_ONLY


async def test_invited_mode_rejects_an_inactive_ad_link(
    use_case: CheckRegistrationAccessUseCase,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        link = await ad_link_repository.create(CreateAdLinkDto(name="off", code="offlink"))
        await ad_link_repository.update(UpdateAdLinkDto(ad_link_id=link.id, is_active=False))
    await _set(settings_repository, uow, mode=AccessMode.INVITED)

    assert await _check(use_case, ad_link_code="offlink") is AccessDenial.INVITE_ONLY


async def test_invited_mode_webcabinet_channel_needs_allow_webcabinet(
    use_case: CheckRegistrationAccessUseCase,
    settings_repository: SettingsRepository,
    ad_link_repository: AdLinkRepository,
    uow: UnitOfWork,
) -> None:
    async with uow:
        await ad_link_repository.create(
            CreateAdLinkDto(name="no web", code="noweb", allow_webcabinet=False)
        )
    await _set(settings_repository, uow, mode=AccessMode.INVITED)

    result = await _check(use_case, ad_link_code="noweb", channel=AdLinkChannel.WEBCABINET)
    assert result is AccessDenial.INVITE_ONLY
