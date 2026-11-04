from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastCategory, BroadcastDelivery, EmailOutcome, Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.modules.broadcasts.dto import (
    BroadcastDto,
    BroadcastEmailContentDto,
    PreviewBroadcastEmailDto,
    SendTestBroadcastEmailDto,
)
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import email_image_path
from app.modules.broadcasts.usecases import (
    PreviewBroadcastEmailUseCase,
    SendTestBroadcastEmailUseCase,
)
from app.modules.email import EmailDeliveryDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.settings import GetPublicAppearanceImageUseCase
from app.modules.settings.dto import UpdateEmailSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.translations.repository import TranslationRepository
from app.modules.users import UserDto
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.broadcasts.test_email_delivery import FakeBatchSender
from tests.modules.broadcasts.test_repository import save_dto


@pytest.fixture
def media_config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


@pytest.fixture
def make_preview(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
) -> Callable[[], PreviewBroadcastEmailUseCase]:
    return lambda: PreviewBroadcastEmailUseCase(
        broadcast_repository,
        settings_repository,
        promocode_repository,
        translation_repository,
        GetPublicAppearanceImageUseCase(settings_repository, media_config, uow),
        media_config,
        uow,
    )


@pytest.fixture
def make_test_send(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
) -> Callable[[FakeBatchSender], SendTestBroadcastEmailUseCase]:
    return lambda sender: SendTestBroadcastEmailUseCase(
        broadcast_repository,
        settings_repository,
        promocode_repository,
        translation_repository,
        GetPublicAppearanceImageUseCase(settings_repository, media_config, uow),
        sender,  # type: ignore[arg-type]
        media_config,
        uow,
    )


@pytest.fixture
async def admin(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="Alice", role=Role.ADMIN, login="email-preview", language=Locale.EN)
    )


@pytest.fixture
async def smtp(settings_repository: SettingsRepository) -> None:
    await settings_repository.update_email_settings(
        UpdateEmailSettingsDto(host="smtp.example.com", from_address="shop@example.com")
    )


async def _broadcast(
    repository: BroadcastRepository,
    contents: Optional[dict[Locale, BroadcastEmailContentDto]] = None,
    **kw: Any,
) -> BroadcastDto:
    if contents is None:
        contents = {Locale.EN: BroadcastEmailContentDto(subject="Hi { $name }", html="<p>Yo</p>")}
    return await repository.create(
        save_dto(delivery=BroadcastDelivery.EMAIL, email_contents=contents, **kw),
        created_by=None,
    )


async def test_preview_inlines_images_and_samples_variables(
    broadcast_repository: BroadcastRepository,
    make_preview: Callable[[], PreviewBroadcastEmailUseCase],
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    created = await _broadcast(broadcast_repository)
    image = await broadcast_repository.add_email_image(created.id, "image/png", "png", 3)
    path = email_image_path(media_config.media_dir, created.id, image.id, "png")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"png")
    await broadcast_repository.replace(
        created.id,
        save_dto(
            delivery=BroadcastDelivery.EMAIL,
            email_contents={
                Locale.EN: BroadcastEmailContentDto(
                    subject="Hi { $name }",
                    html="<p>{ $plan } { $days_left }</p>" + f'<img src="bc-image:{image.id}">',
                )
            },
        ),
    )

    result = await make_preview()(
        admin, PreviewBroadcastEmailDto(broadcast_id=created.id, locale=Locale.EN)
    )

    assert result.subject == "Hi Anna"
    assert "data:image/png;base64,cG5n" in result.html
    assert "cid:" not in result.html
    assert "Pro" in result.html and "4" in result.html


async def test_preview_falls_back_to_default_locale(
    broadcast_repository: BroadcastRepository,
    make_preview: Callable[[], PreviewBroadcastEmailUseCase],
    admin: UserDto,
) -> None:
    created = await _broadcast(broadcast_repository)
    result = await make_preview()(
        admin, PreviewBroadcastEmailDto(broadcast_id=created.id, locale=Locale.RU)
    )
    assert result.subject == "Hi Анна"


async def test_preview_shows_unsubscribe_without_cabinet_url(
    broadcast_repository: BroadcastRepository,
    make_preview: Callable[[], PreviewBroadcastEmailUseCase],
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    media_config.cabinet = media_config.cabinet.model_copy(update={"domain": None})
    created = await _broadcast(broadcast_repository, category=BroadcastCategory.MARKETING)
    result = await make_preview()(
        admin, PreviewBroadcastEmailDto(broadcast_id=created.id, locale=Locale.EN)
    )
    assert 'href="#"' in result.html


async def test_preview_without_email_content_is_default_locale_missing(
    broadcast_repository: BroadcastRepository,
    make_preview: Callable[[], PreviewBroadcastEmailUseCase],
    admin: UserDto,
) -> None:
    created = await broadcast_repository.create(save_dto(), created_by=None)
    with pytest.raises(ValidationError) as caught:
        await make_preview()(
            admin, PreviewBroadcastEmailDto(broadcast_id=created.id, locale=Locale.EN)
        )
    assert caught.value.code == ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING


async def test_test_send_mails_the_address_through_the_bulk_profile(
    broadcast_repository: BroadcastRepository,
    make_test_send: Callable[[FakeBatchSender], SendTestBroadcastEmailUseCase],
    admin: UserDto,
    smtp: None,
) -> None:
    created = await _broadcast(broadcast_repository, category=BroadcastCategory.SERVICE)
    sender = FakeBatchSender()

    await make_test_send(sender)(
        admin,
        SendTestBroadcastEmailDto(broadcast_id=created.id, locale=Locale.EN, to="me@example.com"),
    )

    [email] = sender.sent
    assert email.to == "me@example.com"
    assert email.subject == "Hi Alice"
    assert [p.host for p in sender.profiles] == ["smtp.example.com"]


async def test_test_send_refused_is_test_failed(
    broadcast_repository: BroadcastRepository,
    make_test_send: Callable[[FakeBatchSender], SendTestBroadcastEmailUseCase],
    admin: UserDto,
    smtp: None,
) -> None:
    created = await _broadcast(broadcast_repository)
    sender = FakeBatchSender(
        {"me@example.com": EmailDeliveryDto(outcome=EmailOutcome.REFUSED, error="550")}
    )
    with pytest.raises(ValidationError) as caught:
        await make_test_send(sender)(
            admin,
            SendTestBroadcastEmailDto(
                broadcast_id=created.id, locale=Locale.EN, to="me@example.com"
            ),
        )
    assert caught.value.code == ErrorCode.BROADCAST_TEST_FAILED


async def test_test_send_connection_error_is_test_failed(
    broadcast_repository: BroadcastRepository,
    make_test_send: Callable[[FakeBatchSender], SendTestBroadcastEmailUseCase],
    admin: UserDto,
    smtp: None,
) -> None:
    created = await _broadcast(broadcast_repository)
    with pytest.raises(ValidationError) as caught:
        await make_test_send(FakeBatchSender(connect_error=True))(
            admin,
            SendTestBroadcastEmailDto(
                broadcast_id=created.id, locale=Locale.EN, to="me@example.com"
            ),
        )
    assert caught.value.code == ErrorCode.BROADCAST_TEST_FAILED


async def test_test_send_without_smtp_is_not_configured(
    broadcast_repository: BroadcastRepository,
    make_test_send: Callable[[FakeBatchSender], SendTestBroadcastEmailUseCase],
    admin: UserDto,
) -> None:
    created = await _broadcast(broadcast_repository)
    sender = FakeBatchSender()
    with pytest.raises(ValidationError) as caught:
        await make_test_send(sender)(
            admin,
            SendTestBroadcastEmailDto(
                broadcast_id=created.id, locale=Locale.EN, to="me@example.com"
            ),
        )
    assert caught.value.code == ErrorCode.EMAIL_NOT_CONFIGURED
    assert sender.sent == []


async def test_preview_missing_image_file_is_image_invalid(
    broadcast_repository: BroadcastRepository,
    make_preview: Callable[[], PreviewBroadcastEmailUseCase],
    admin: UserDto,
) -> None:
    created = await _broadcast(broadcast_repository)
    image = await broadcast_repository.add_email_image(created.id, "image/png", "png", 3)
    await broadcast_repository.replace(
        created.id,
        save_dto(
            delivery=BroadcastDelivery.EMAIL,
            email_contents={
                Locale.EN: BroadcastEmailContentDto(
                    subject="Hi", html=f'<img src="bc-image:{image.id}">'
                )
            },
        ),
    )
    with pytest.raises(ValidationError) as caught:
        await make_preview()(
            admin, PreviewBroadcastEmailDto(broadcast_id=created.id, locale=Locale.EN)
        )
    assert caught.value.code == ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID


async def test_preview_unknown_image_id_is_image_invalid(
    broadcast_repository: BroadcastRepository,
    make_preview: Callable[[], PreviewBroadcastEmailUseCase],
    admin: UserDto,
) -> None:
    created = await _broadcast(
        broadcast_repository,
        contents={
            Locale.EN: BroadcastEmailContentDto(subject="Hi", html='<img src="bc-image:999999">')
        },
    )
    with pytest.raises(ValidationError) as caught:
        await make_preview()(
            admin, PreviewBroadcastEmailDto(broadcast_id=created.id, locale=Locale.EN)
        )
    assert caught.value.code == ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID


async def test_test_send_unknown_image_id_is_image_invalid(
    broadcast_repository: BroadcastRepository,
    make_test_send: Callable[[FakeBatchSender], SendTestBroadcastEmailUseCase],
    admin: UserDto,
    smtp: None,
) -> None:
    created = await _broadcast(
        broadcast_repository,
        contents={
            Locale.EN: BroadcastEmailContentDto(subject="Hi", html='<img src="bc-image:999999">')
        },
    )
    sender = FakeBatchSender()
    with pytest.raises(ValidationError) as caught:
        await make_test_send(sender)(
            admin,
            SendTestBroadcastEmailDto(
                broadcast_id=created.id, locale=Locale.EN, to="me@example.com"
            ),
        )
    assert caught.value.code == ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID
    assert sender.sent == []


async def test_test_send_missing_image_file_is_image_invalid(
    broadcast_repository: BroadcastRepository,
    make_test_send: Callable[[FakeBatchSender], SendTestBroadcastEmailUseCase],
    admin: UserDto,
    smtp: None,
) -> None:
    created = await _broadcast(broadcast_repository)
    image = await broadcast_repository.add_email_image(created.id, "image/png", "png", 3)
    await broadcast_repository.replace(
        created.id,
        save_dto(
            delivery=BroadcastDelivery.EMAIL,
            email_contents={
                Locale.EN: BroadcastEmailContentDto(
                    subject="Hi", html=f'<img src="bc-image:{image.id}">'
                )
            },
        ),
    )
    with pytest.raises(ValidationError) as caught:
        await make_test_send(FakeBatchSender())(
            admin,
            SendTestBroadcastEmailDto(
                broadcast_id=created.id, locale=Locale.EN, to="me@example.com"
            ),
        )
    assert caught.value.code == ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID
