import os
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Final

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import SyntheticActor
from app.core.config import AppConfig
from app.core.config.cabinet import CabinetConfig
from app.core.db.models.broadcast import BroadcastRecipient
from app.core.db.models.promocode import PromocodeActivation
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    BroadcastCategory,
    BroadcastDelivery,
    BroadcastMediaType,
    BroadcastRecipientStatus,
    BroadcastStatus,
    Locale,
    PromocodeRewardType,
    Role,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission, PermissionPolicy, expand_token_scopes
from app.core.utils.time import datetime_now
from app.modules.broadcasts.dto import (
    BroadcastAudienceDto,
    BroadcastContentDto,
    BroadcastDto,
    BroadcastEmailContentDto,
    PreviewAudienceDto,
    SendBroadcastDto,
    SetBroadcastMediaDto,
    UpdateBroadcastDto,
)
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import media_path
from app.modules.broadcasts.usecases import (
    CancelBroadcastUseCase,
    CreateBroadcastUseCase,
    DeleteBroadcastMediaUseCase,
    DeleteBroadcastUseCase,
    GetBroadcastPromocodeUseCase,
    GetBroadcastSummaryUseCase,
    PreviewBroadcastAudienceUseCase,
    RecallBroadcastUseCase,
    RetryBroadcastUseCase,
    SendBroadcastUseCase,
    SendTestBroadcastUseCase,
    SetBroadcastMediaUseCase,
    UpdateBroadcastUseCase,
)
from app.modules.broadcasts.validation import promocode_is_usable
from app.modules.promocodes.dto import CreatePromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.settings.dto import UpdateBotSettingsDto, UpdateEmailSettingsDto
from app.modules.settings.repository import SettingsRepository
from app.modules.translations.repository import TranslationRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.broadcasts.factories import MockTelegram, make_customer, ok_response
from tests.modules.broadcasts.test_repository import save_dto

_MB = 1024 * 1024


@pytest.fixture
async def admin(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="admin", role=Role.ADMIN, login="bc-admin")
    )


@pytest.fixture
def media_config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


@pytest.fixture
def create_use_case(
    broadcast_repository: BroadcastRepository,
    promocode_repository: PromocodeRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> CreateBroadcastUseCase:
    return CreateBroadcastUseCase(broadcast_repository, promocode_repository, uow, event_publisher)


@pytest.fixture
def update_use_case(
    broadcast_repository: BroadcastRepository,
    promocode_repository: PromocodeRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> UpdateBroadcastUseCase:
    return UpdateBroadcastUseCase(
        broadcast_repository, promocode_repository, media_config, uow, event_publisher
    )


@pytest.fixture
def media_use_case(
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> SetBroadcastMediaUseCase:
    return SetBroadcastMediaUseCase(broadcast_repository, media_config, uow, event_publisher)


@pytest.fixture
def delete_use_case(
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> DeleteBroadcastUseCase:
    return DeleteBroadcastUseCase(broadcast_repository, media_config, uow, event_publisher)


async def _make(
    repository: BroadcastRepository, status: BroadcastStatus = BroadcastStatus.DRAFT, **overrides
) -> BroadcastDto:
    created = await repository.create(save_dto(**overrides), created_by=None)
    if status is not BroadcastStatus.DRAFT:
        fields: dict[str, object] = {"status": status}
        if status is BroadcastStatus.SCHEDULED:
            fields["scheduled_at"] = datetime_now()
        await repository.update_fields(created.id, **fields)
    return await repository.get_by_id(created.id)


def _upload(data: bytes) -> Path:
    # what the router leaves for the usecase: the streamed body in a temp file
    fd, name = tempfile.mkstemp(suffix=".part")
    os.write(fd, data)
    os.close(fd)
    return Path(name)


def _media(broadcast_id: int, content_type: str, data: bytes) -> SetBroadcastMediaDto:
    return SetBroadcastMediaDto(
        broadcast_id=broadcast_id,
        content_type=content_type,
        source=_upload(data),
        size=len(data),
    )


def _photo(broadcast_id: int, size: int = 100) -> SetBroadcastMediaDto:
    return _media(broadcast_id, "image/jpeg", b"\xff" * size)


async def test_create_stores_draft_with_creator(
    create_use_case: CreateBroadcastUseCase, admin: UserDto
) -> None:
    created = await create_use_case(admin, save_dto())
    assert created.status is BroadcastStatus.DRAFT
    assert created.created_by == admin.id


async def test_create_rejects_unknown_plan(
    create_use_case: CreateBroadcastUseCase, admin: UserDto
) -> None:
    with pytest.raises(ValidationError) as error:
        await create_use_case(admin, save_dto(audience=BroadcastAudienceDto(plan_ids=[999_999])))
    assert error.value.code is ErrorCode.BROADCAST_AUDIENCE_INVALID


async def test_create_rejects_unusable_promocode(
    create_use_case: CreateBroadcastUseCase,
    promocode_repository: PromocodeRepository,
    admin: UserDto,
) -> None:
    promo = await promocode_repository.create(
        CreatePromocodeDto(code="BCEXPIRED", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    await promocode_repository.delete(promo.id)
    with pytest.raises(ValidationError) as error:
        await create_use_case(admin, save_dto(promocode_id=promo.id))
    assert error.value.code is ErrorCode.BROADCAST_PROMOCODE_UNUSABLE


async def test_create_requires_permission(create_use_case: CreateBroadcastUseCase) -> None:
    user = UserDto(id=77, name="u", role=Role.USER, language=Locale.EN)
    with pytest.raises(PermissionDeniedError):
        await create_use_case(user, save_dto())


async def test_update_of_scheduled_returns_to_draft(
    update_use_case: UpdateBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    scheduled = await _make(broadcast_repository, BroadcastStatus.SCHEDULED)
    updated = await update_use_case(
        admin,
        UpdateBroadcastDto(
            broadcast_id=scheduled.id,
            data=save_dto(contents={Locale.EN: BroadcastContentDto(text="Changed")}),
        ),
    )
    assert updated.status is BroadcastStatus.DRAFT
    assert updated.scheduled_at is None
    assert updated.contents[Locale.EN].text == "Changed"


async def test_update_while_sending_is_refused(
    update_use_case: UpdateBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    sending = await _make(broadcast_repository, BroadcastStatus.SENDING)
    with pytest.raises(ConflictError) as error:
        await update_use_case(admin, UpdateBroadcastDto(broadcast_id=sending.id, data=save_dto()))
    assert error.value.code is ErrorCode.BROADCAST_INVALID_STATUS


async def test_photo_media_sets_type_and_caption_limit(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    short = await _make(broadcast_repository)
    updated = await media_use_case(admin, _photo(short.id))
    assert updated.media_type is BroadcastMediaType.PHOTO
    assert updated.media_extension == "jpg"
    assert updated.media_size_bytes == 100
    path = media_path(media_config.media_dir, short.id, 1, "jpg")
    assert path.read_bytes() == b"\xff" * 100


async def test_media_rejects_text_over_caption_limit(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    long_text = await _make(
        broadcast_repository, contents={Locale.EN: BroadcastContentDto(text="a" * 2000)}
    )
    with pytest.raises(ValidationError) as error:
        await media_use_case(admin, _photo(long_text.id))
    assert error.value.code is ErrorCode.BROADCAST_TEXT_TOO_LONG


async def test_media_rejects_oversized_photo(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    broadcast = await _make(broadcast_repository)
    with pytest.raises(ValidationError) as error:
        await media_use_case(admin, _photo(broadcast.id, size=10 * _MB + 1))
    assert error.value.code is ErrorCode.BROADCAST_MEDIA_INVALID
    assert not media_path(media_config.media_dir, broadcast.id, 1, "jpg").exists()


async def test_media_rejects_unknown_content_type(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    broadcast = await _make(broadcast_repository)
    with pytest.raises(ValidationError) as error:
        await media_use_case(
            admin,
            _media(broadcast.id, "application/x-msdownload", b"x"),
        )
    assert error.value.code is ErrorCode.BROADCAST_MEDIA_INVALID


async def test_media_of_scheduled_returns_to_draft(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    scheduled = await _make(broadcast_repository, BroadcastStatus.SCHEDULED)
    updated = await media_use_case(admin, _photo(scheduled.id))
    assert updated.status is BroadcastStatus.DRAFT
    assert updated.scheduled_at is None


async def test_replacing_media_with_other_type_removes_old_file(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    broadcast = await _make(broadcast_repository)
    await media_use_case(admin, _photo(broadcast.id))
    updated = await media_use_case(
        admin,
        _media(broadcast.id, "video/mp4", b"v"),
    )
    assert updated.media_type is BroadcastMediaType.VIDEO
    assert not media_path(media_config.media_dir, broadcast.id, 1, "jpg").exists()
    assert media_path(media_config.media_dir, broadcast.id, 2, "mp4").exists()


async def test_two_media_sets_in_a_row_leave_only_the_second_file(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    broadcast = await _make(broadcast_repository)
    await media_use_case(admin, _photo(broadcast.id))
    updated = await media_use_case(admin, _photo(broadcast.id))
    assert updated.media_version == 2
    files = sorted(
        p.name for p in (media_config.media_dir / "broadcasts").glob(f"{broadcast.id}_*")
    )
    assert files == [f"{broadcast.id}_2.jpg"]


async def test_delete_media_refuses_when_texts_would_be_empty(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    admin: UserDto,
) -> None:
    broadcast = await _make(
        broadcast_repository, contents={Locale.EN: BroadcastContentDto(text="")}
    )
    await media_use_case(admin, _photo(broadcast.id))
    with pytest.raises(ValidationError) as error:
        await DeleteBroadcastMediaUseCase(broadcast_repository, media_config, uow, event_publisher)(
            admin, broadcast.id
        )
    assert error.value.code is ErrorCode.BROADCAST_DEFAULT_LOCALE_MISSING
    kept = await broadcast_repository.get_by_id(broadcast.id)
    assert kept.media_extension == "jpg"
    assert media_path(media_config.media_dir, broadcast.id, 1, "jpg").exists()


async def test_delete_media_refuses_when_another_locale_would_be_empty(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    admin: UserDto,
) -> None:
    broadcast = await _make(
        broadcast_repository,
        contents={
            Locale.EN: BroadcastContentDto(text="Hi"),
            Locale.RU: BroadcastContentDto(text=""),
        },
    )
    await media_use_case(admin, _photo(broadcast.id))
    with pytest.raises(ValidationError) as error:
        await DeleteBroadcastMediaUseCase(broadcast_repository, media_config, uow, event_publisher)(
            admin, broadcast.id
        )
    assert error.value.code is ErrorCode.BROADCAST_TEXT_EMPTY


async def test_delete_media_clears_fields_and_file(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    admin: UserDto,
) -> None:
    broadcast = await _make(broadcast_repository)
    await media_use_case(admin, _photo(broadcast.id))
    cleared = await DeleteBroadcastMediaUseCase(
        broadcast_repository, media_config, uow, event_publisher
    )(admin, broadcast.id)
    assert cleared.media_type is None
    assert cleared.media_extension is None
    assert not media_path(media_config.media_dir, broadcast.id, 1, "jpg").exists()


async def test_delete_removes_media_file(
    delete_use_case: DeleteBroadcastUseCase,
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    broadcast = await _make(broadcast_repository)
    await media_use_case(admin, _photo(broadcast.id))
    path = media_path(media_config.media_dir, broadcast.id, 1, "jpg")
    assert path.exists()
    await delete_use_case(admin, broadcast.id)
    assert not path.exists()
    assert await broadcast_repository.find_by_id(broadcast.id) is None


async def test_delete_while_sending_is_refused(
    delete_use_case: DeleteBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    sending = await _make(broadcast_repository, BroadcastStatus.SENDING)
    with pytest.raises(ConflictError) as error:
        await delete_use_case(admin, sending.id)
    assert error.value.code is ErrorCode.BROADCAST_INVALID_STATUS


async def test_preview_counts_by_locale(
    session,
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    uow: UnitOfWork,
    admin: UserDto,
) -> None:
    a = await make_customer(user_repository, session, telegram_id=9201, language=Locale.EN)
    b = await make_customer(user_repository, session, telegram_id=9202, language=Locale.EN)
    c = await make_customer(user_repository, session, telegram_id=9203, language=Locale.RU)
    preview = await PreviewBroadcastAudienceUseCase(broadcast_repository, uow)(
        admin,
        PreviewAudienceDto(
            audience=BroadcastAudienceDto(user_ids=[a, b, c]),
            category=save_dto().category,
        ),
    )
    assert preview.total == 3
    assert preview.by_locale == {Locale.EN: 2, Locale.RU: 1}


def test_token_actor_cannot_send_but_can_create() -> None:
    token = SyntheticActor(
        id=0,
        role=Role.USER,
        name="token",
        is_privileged=True,
        log="[token]",
        permission_grants=[p.value for p in expand_token_scopes(["broadcasts:*"])],
    )
    assert PermissionPolicy.has_permission(token, Permission.BROADCASTS_CREATE)
    assert PermissionPolicy.has_permission(token, Permission.BROADCASTS_UPDATE)
    assert not PermissionPolicy.has_permission(token, Permission.BROADCASTS_SEND)


async def test_promocode_is_usable_respects_max_activations(
    session,
    user_repository: UserRepository,
    promocode_repository: PromocodeRepository,
) -> None:
    promo = await promocode_repository.create(
        CreatePromocodeDto(
            code="BCLIMIT",
            reward_type=PromocodeRewardType.DURATION,
            reward=5,
            max_activations=1,
        )
    )
    assert await promocode_is_usable(promocode_repository, promo.id) == "BCLIMIT"
    user_id = await make_customer(user_repository, session, telegram_id=9301)
    session.add(PromocodeActivation(promocode_id=promo.id, user_id=user_id))
    await session.flush()
    assert await promocode_is_usable(promocode_repository, promo.id) is None


@pytest.fixture
def start_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def recall_dispatch() -> RecordingDispatch:
    return RecordingDispatch()


@pytest.fixture
def send_use_case(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    config: AppConfig,
    start_dispatch: RecordingDispatch,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> SendBroadcastUseCase:
    return SendBroadcastUseCase(
        broadcast_repository, settings_repository, config, start_dispatch, uow, event_publisher
    )


@pytest.fixture
def cancel_use_case(
    broadcast_repository: BroadcastRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> CancelBroadcastUseCase:
    return CancelBroadcastUseCase(broadcast_repository, uow, event_publisher)


@pytest.fixture
def retry_use_case(
    broadcast_repository: BroadcastRepository,
    start_dispatch: RecordingDispatch,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> RetryBroadcastUseCase:
    return RetryBroadcastUseCase(broadcast_repository, start_dispatch, uow, event_publisher)


@pytest.fixture
def recall_use_case(
    broadcast_repository: BroadcastRepository,
    recall_dispatch: RecordingDispatch,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> RecallBroadcastUseCase:
    return RecallBroadcastUseCase(broadcast_repository, recall_dispatch, uow, event_publisher)


@pytest.fixture
async def with_token(settings_repository: SettingsRepository) -> None:
    await settings_repository.update_bot_settings(UpdateBotSettingsDto(token="123:abc"))


async def _recipients(
    session: AsyncSession,
    repository: BroadcastRepository,
    user_repository: UserRepository,
    broadcast: BroadcastDto,
    statuses: list[BroadcastRecipientStatus],
    base_telegram_id: int,
) -> list[int]:
    user_ids = [
        await make_customer(user_repository, session, telegram_id=base_telegram_id + i)
        for i in range(len(statuses))
    ]
    await repository.materialize(
        broadcast.id,
        BroadcastAudienceDto(user_ids=user_ids),
        broadcast.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )
    rows = await session.scalars(
        select(BroadcastRecipient)
        .where(BroadcastRecipient.broadcast_id == broadcast.id)
        .order_by(BroadcastRecipient.id)
    )
    ids = [row.id for row in rows]
    for recipient_id, status in zip(ids, statuses, strict=True):
        await repository.mark_recipient(recipient_id, status)
    return ids


async def _statuses(session: AsyncSession, broadcast_id: int) -> list[BroadcastRecipientStatus]:
    rows = await session.scalars(
        select(BroadcastRecipient.status)
        .where(BroadcastRecipient.broadcast_id == broadcast_id)
        .order_by(BroadcastRecipient.id)
    )
    return list(rows)


async def test_send_now_schedules_and_kicks_start(
    send_use_case: SendBroadcastUseCase,
    start_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
    with_token: None,
) -> None:
    draft = await _make(broadcast_repository)
    result = await send_use_case(admin, SendBroadcastDto(broadcast_id=draft.id))
    assert result.status is BroadcastStatus.SCHEDULED
    assert start_dispatch.messages == [{"broadcast_id": draft.id}]


async def test_send_later_does_not_kick(
    send_use_case: SendBroadcastUseCase,
    start_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
    with_token: None,
) -> None:
    draft = await _make(broadcast_repository)
    later = datetime_now() + timedelta(hours=1)
    result = await send_use_case(admin, SendBroadcastDto(broadcast_id=draft.id, scheduled_at=later))
    assert result.status is BroadcastStatus.SCHEDULED
    assert result.scheduled_at == later
    assert start_dispatch.messages == []


async def test_send_in_past_refused(
    send_use_case: SendBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
    with_token: None,
) -> None:
    draft = await _make(broadcast_repository)
    past = datetime_now() - timedelta(minutes=10)
    with pytest.raises(ValidationError) as caught:
        await send_use_case(admin, SendBroadcastDto(broadcast_id=draft.id, scheduled_at=past))
    assert caught.value.code == ErrorCode.BROADCAST_SCHEDULE_IN_PAST


async def test_send_requires_bot_token(
    send_use_case: SendBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    draft = await _make(broadcast_repository)
    with pytest.raises(ValidationError) as caught:
        await send_use_case(admin, SendBroadcastDto(broadcast_id=draft.id))
    assert caught.value.code == ErrorCode.BROADCAST_BOT_NOT_CONFIGURED


_EMAIL_ONLY: Final[dict[str, object]] = {
    "delivery": BroadcastDelivery.EMAIL,
    "email_contents": {Locale.EN: BroadcastEmailContentDto(subject="Hi", html="<p>x</p>")},
}


@pytest.fixture
async def with_smtp(settings_repository: SettingsRepository) -> None:
    await settings_repository.update_email_settings(
        UpdateEmailSettingsDto(host="smtp.example.com", from_address="shop@example.com")
    )


async def test_send_email_only_without_bot_token(
    send_use_case: SendBroadcastUseCase,
    start_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
    with_smtp: None,
) -> None:
    draft = await _make(broadcast_repository, **_EMAIL_ONLY)
    result = await send_use_case(admin, SendBroadcastDto(broadcast_id=draft.id))
    assert result.status is BroadcastStatus.SCHEDULED
    assert start_dispatch.messages == [{"broadcast_id": draft.id}]


async def test_send_email_without_smtp_fails(
    send_use_case: SendBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    draft = await _make(broadcast_repository, **_EMAIL_ONLY)
    with pytest.raises(ValidationError) as caught:
        await send_use_case(admin, SendBroadcastDto(broadcast_id=draft.id))
    assert caught.value.code == ErrorCode.EMAIL_NOT_CONFIGURED


async def test_send_marketing_email_without_cabinet_url_fails(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    config: AppConfig,
    start_dispatch: RecordingDispatch,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    admin: UserDto,
    with_smtp: None,
) -> None:
    use_case = SendBroadcastUseCase(
        broadcast_repository,
        settings_repository,
        config.model_copy(update={"cabinet": CabinetConfig(domain=None)}),
        start_dispatch,
        uow,
        event_publisher,
    )
    draft = await _make(broadcast_repository, category=BroadcastCategory.MARKETING, **_EMAIL_ONLY)
    with pytest.raises(ValidationError) as caught:
        await use_case(admin, SendBroadcastDto(broadcast_id=draft.id))
    assert caught.value.code == ErrorCode.BROADCAST_UNSUBSCRIBE_URL_MISSING


async def test_send_service_email_without_cabinet_url_ok(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    config: AppConfig,
    start_dispatch: RecordingDispatch,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    admin: UserDto,
    with_smtp: None,
) -> None:
    use_case = SendBroadcastUseCase(
        broadcast_repository,
        settings_repository,
        config.model_copy(update={"cabinet": CabinetConfig(domain=None)}),
        start_dispatch,
        uow,
        event_publisher,
    )
    draft = await _make(broadcast_repository, category=BroadcastCategory.SERVICE, **_EMAIL_ONLY)
    result = await use_case(admin, SendBroadcastDto(broadcast_id=draft.id))
    assert result.status is BroadcastStatus.SCHEDULED


async def test_send_to_channel_requires_channel(
    send_use_case: SendBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
    with_token: None,
) -> None:
    draft = await _make(broadcast_repository, post_to_channel=True)
    with pytest.raises(ValidationError) as caught:
        await send_use_case(admin, SendBroadcastDto(broadcast_id=draft.id))
    assert caught.value.code == ErrorCode.BROADCAST_CHANNEL_NOT_CONFIGURED


async def test_send_twice_refused(
    send_use_case: SendBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
    with_token: None,
) -> None:
    draft = await _make(broadcast_repository)
    await send_use_case(admin, SendBroadcastDto(broadcast_id=draft.id))
    with pytest.raises(ConflictError) as caught:
        await send_use_case(admin, SendBroadcastDto(broadcast_id=draft.id))
    assert caught.value.code == ErrorCode.BROADCAST_INVALID_STATUS


async def test_cancel_scheduled_and_sending(
    session: AsyncSession,
    cancel_use_case: CancelBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    user_repository: UserRepository,
    admin: UserDto,
) -> None:
    scheduled = await _make(broadcast_repository, BroadcastStatus.SCHEDULED)
    result = await cancel_use_case(admin, scheduled.id)
    assert result.status is BroadcastStatus.CANCELED
    assert result.scheduled_at is None
    assert result.completed_at is not None

    sending = await _make(broadcast_repository, BroadcastStatus.SENDING)
    await _recipients(
        session,
        broadcast_repository,
        user_repository,
        sending,
        [BroadcastRecipientStatus.PENDING, BroadcastRecipientStatus.PENDING],
        9410,
    )
    result = await cancel_use_case(admin, sending.id)
    assert result.status is BroadcastStatus.CANCELED
    assert result.completed_at is not None
    assert await _statuses(session, sending.id) == [BroadcastRecipientStatus.CANCELED] * 2


async def test_cancel_draft_refused(
    cancel_use_case: CancelBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    draft = await _make(broadcast_repository)
    with pytest.raises(ConflictError) as caught:
        await cancel_use_case(admin, draft.id)
    assert caught.value.code == ErrorCode.BROADCAST_INVALID_STATUS


async def test_retry_resets_failed_only(
    session: AsyncSession,
    retry_use_case: RetryBroadcastUseCase,
    start_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    user_repository: UserRepository,
    admin: UserDto,
) -> None:
    done = await _make(broadcast_repository, BroadcastStatus.COMPLETED)
    await broadcast_repository.update_fields(done.id, completed_at=datetime_now())
    await _recipients(
        session,
        broadcast_repository,
        user_repository,
        done,
        [BroadcastRecipientStatus.FAILED, BroadcastRecipientStatus.BLOCKED],
        9420,
    )
    result = await retry_use_case(admin, done.id)
    assert result.status is BroadcastStatus.SCHEDULED
    assert result.completed_at is None
    assert result.failed_count == 0
    assert result.blocked_count == 1
    assert start_dispatch.messages == [{"broadcast_id": done.id}]
    assert await _statuses(session, done.id) == [
        BroadcastRecipientStatus.PENDING,
        BroadcastRecipientStatus.BLOCKED,
    ]


async def test_retry_without_failed_refused(
    session: AsyncSession,
    retry_use_case: RetryBroadcastUseCase,
    start_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    user_repository: UserRepository,
    admin: UserDto,
) -> None:
    done = await _make(broadcast_repository, BroadcastStatus.COMPLETED)
    await _recipients(
        session, broadcast_repository, user_repository, done, [BroadcastRecipientStatus.SENT], 9430
    )
    with pytest.raises(ConflictError) as caught:
        await retry_use_case(admin, done.id)
    assert caught.value.code == ErrorCode.BROADCAST_INVALID_STATUS
    assert start_dispatch.messages == []


async def test_recall_after_48h_refused(
    recall_use_case: RecallBroadcastUseCase,
    recall_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    done = await _make(broadcast_repository, BroadcastStatus.COMPLETED)
    await broadcast_repository.update_fields(
        done.id, started_at=datetime_now() - timedelta(hours=49)
    )
    with pytest.raises(ValidationError) as caught:
        await recall_use_case(admin, done.id)
    assert caught.value.code == ErrorCode.BROADCAST_RECALL_EXPIRED
    assert recall_dispatch.messages == []


async def test_recall_cancels_sending_and_kicks(
    session: AsyncSession,
    recall_use_case: RecallBroadcastUseCase,
    recall_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    user_repository: UserRepository,
    admin: UserDto,
) -> None:
    sending = await _make(broadcast_repository, BroadcastStatus.SENDING)
    await broadcast_repository.update_fields(sending.id, started_at=datetime_now())
    await _recipients(
        session,
        broadcast_repository,
        user_repository,
        sending,
        [BroadcastRecipientStatus.SENT, BroadcastRecipientStatus.PENDING],
        9440,
    )
    result = await recall_use_case(admin, sending.id)
    assert result.status is BroadcastStatus.CANCELED
    assert result.completed_at is not None
    assert recall_dispatch.messages == [{"broadcast_id": sending.id}]
    assert await _statuses(session, sending.id) == [
        BroadcastRecipientStatus.SENT,
        BroadcastRecipientStatus.CANCELED,
    ]


async def test_recall_without_start_refused(
    recall_use_case: RecallBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    done = await _make(broadcast_repository, BroadcastStatus.CANCELED)
    with pytest.raises(ConflictError) as caught:
        await recall_use_case(admin, done.id)
    assert caught.value.code == ErrorCode.BROADCAST_INVALID_STATUS


def _test_use_case(
    telegram: MockTelegram,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
) -> SendTestBroadcastUseCase:
    return SendTestBroadcastUseCase(
        broadcast_repository,
        settings_repository,
        promocode_repository,
        translation_repository,
        telegram,
        media_config,
        uow,
    )


async def test_test_send_requires_telegram(
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    admin: UserDto,
    with_token: None,
) -> None:
    telegram = MockTelegram(ok_response)
    use_case = _test_use_case(
        telegram,
        broadcast_repository,
        settings_repository,
        promocode_repository,
        translation_repository,
        media_config,
        uow,
    )
    draft = await _make(broadcast_repository)
    with pytest.raises(ValidationError) as caught:
        await use_case(admin, draft.id)
    assert caught.value.code == ErrorCode.BROADCAST_TEST_NO_TELEGRAM
    assert telegram.requests == []


async def test_test_send_renders_for_actor(
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    with_token: None,
) -> None:
    actor = await user_repository.create(
        CreateUserDto(name="Alice", role=Role.ADMIN, login="bc-tester", telegram_id=9450)
    )
    telegram = MockTelegram(ok_response)
    use_case = _test_use_case(
        telegram,
        broadcast_repository,
        settings_repository,
        promocode_repository,
        translation_repository,
        media_config,
        uow,
    )
    draft = await _make(broadcast_repository)
    await use_case(actor, draft.id)
    assert len(telegram.requests) == 1
    [sent] = telegram.requests
    assert sent.chat_id == 9450
    assert "Alice" in sent.text


async def test_test_send_failure_is_reported(
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    with_token: None,
) -> None:
    actor = await user_repository.create(
        CreateUserDto(name="Bob", role=Role.ADMIN, login="bc-tester2", telegram_id=9451)
    )
    telegram = MockTelegram(
        lambda request: httpx.Response(400, json={"ok": False, "description": "bad"})
    )
    use_case = _test_use_case(
        telegram,
        broadcast_repository,
        settings_repository,
        promocode_repository,
        translation_repository,
        media_config,
        uow,
    )
    draft = await _make(broadcast_repository)
    with pytest.raises(ValidationError) as caught:
        await use_case(actor, draft.id)
    assert caught.value.code == ErrorCode.BROADCAST_TEST_FAILED


async def test_retry_after_recall_refused(
    session: AsyncSession,
    retry_use_case: RetryBroadcastUseCase,
    start_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    user_repository: UserRepository,
    admin: UserDto,
) -> None:
    done = await _make(broadcast_repository, BroadcastStatus.CANCELED)
    await _recipients(
        session,
        broadcast_repository,
        user_repository,
        done,
        [BroadcastRecipientStatus.FAILED, BroadcastRecipientStatus.RECALLED],
        9460,
    )
    with pytest.raises(ConflictError) as caught:
        await retry_use_case(admin, done.id)
    assert caught.value.code == ErrorCode.BROADCAST_INVALID_STATUS
    assert start_dispatch.messages == []


async def test_test_send_missing_media_is_reported(
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    with_token: None,
) -> None:
    actor = await user_repository.create(
        CreateUserDto(name="Eve", role=Role.ADMIN, login="bc-tester3", telegram_id=9452)
    )
    telegram = MockTelegram(ok_response)
    use_case = _test_use_case(
        telegram,
        broadcast_repository,
        settings_repository,
        promocode_repository,
        translation_repository,
        media_config,
        uow,
    )
    draft = await _make(broadcast_repository)
    await broadcast_repository.update_fields(
        draft.id,
        media_type=BroadcastMediaType.PHOTO,
        media_extension="jpg",
        media_content_type="image/jpeg",
    )
    with pytest.raises(ValidationError) as caught:
        await use_case(actor, draft.id)
    assert caught.value.code == ErrorCode.BROADCAST_TEST_FAILED
    assert telegram.requests == []


async def _add_recipient(
    repository: BroadcastRepository, broadcast: BroadcastDto, customer: UserDto
) -> None:
    await repository.materialize(
        broadcast.id,
        BroadcastAudienceDto(user_ids=[customer.id]),
        broadcast.category,
        BroadcastDelivery.TELEGRAM,
        False,
        datetime_now(),
    )


async def test_broadcast_promocode_for_customer(
    broadcast_repository: BroadcastRepository,
    promocode_repository: PromocodeRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    customer = await user_repository.create(CreateUserDto(name="c", telegram_id=9401))
    use_case = GetBroadcastPromocodeUseCase(broadcast_repository, promocode_repository, uow)
    promo = await promocode_repository.create(
        CreatePromocodeDto(code="SALE", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    broadcast = await broadcast_repository.create(save_dto(promocode_id=promo.id), created_by=None)
    plain = await broadcast_repository.create(save_dto(), created_by=None)
    await _add_recipient(broadcast_repository, broadcast, customer)

    assert await use_case(customer, broadcast.id) is None
    await broadcast_repository.update_fields(broadcast.id, started_at=datetime_now())
    assert await use_case(customer, broadcast.id) == "SALE"
    assert await use_case(customer, plain.id) is None
    assert await use_case(customer, broadcast.id + 1000) is None

    await promocode_repository.delete(promo.id)
    assert await use_case(customer, broadcast.id) is None


async def test_broadcast_promocode_needs_recipient_or_channel_post(
    broadcast_repository: BroadcastRepository,
    promocode_repository: PromocodeRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    recipient = await user_repository.create(CreateUserDto(name="r", telegram_id=9403))
    stranger = await user_repository.create(CreateUserDto(name="s", telegram_id=9404))
    use_case = GetBroadcastPromocodeUseCase(broadcast_repository, promocode_repository, uow)
    promo = await promocode_repository.create(
        CreatePromocodeDto(code="PRIVATE", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    broadcast = await broadcast_repository.create(save_dto(promocode_id=promo.id), created_by=None)
    await _add_recipient(broadcast_repository, broadcast, recipient)
    await broadcast_repository.update_fields(broadcast.id, started_at=datetime_now())

    assert await use_case(recipient, broadcast.id) == "PRIVATE"
    assert await use_case(stranger, broadcast.id) is None

    await broadcast_repository.update_fields(broadcast.id, channel_message_id=77)
    assert await use_case(stranger, broadcast.id) == "PRIVATE"


async def test_broadcast_promocode_is_none_when_deactivated(
    broadcast_repository: BroadcastRepository,
    promocode_repository: PromocodeRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    customer = await user_repository.create(CreateUserDto(name="c", telegram_id=9402))
    use_case = GetBroadcastPromocodeUseCase(broadcast_repository, promocode_repository, uow)
    promo = await promocode_repository.create(
        CreatePromocodeDto(code="OFF", reward_type=PromocodeRewardType.DURATION, reward=5)
    )
    broadcast = await broadcast_repository.create(save_dto(promocode_id=promo.id), created_by=None)
    await _add_recipient(broadcast_repository, broadcast, customer)
    await broadcast_repository.update_fields(broadcast.id, started_at=datetime_now())
    assert await use_case(customer, broadcast.id) == "OFF"

    await promocode_repository.update(UpdatePromocodeDto(promocode_id=promo.id, is_active=False))
    assert await use_case(customer, broadcast.id) is None


async def test_create_with_token_actor_leaves_creator_empty(
    create_use_case: CreateBroadcastUseCase,
) -> None:
    token = SyntheticActor(
        id=0,
        role=Role.USER,
        name="token",
        is_privileged=True,
        log="[token]",
        permission_grants=[p.value for p in expand_token_scopes(["broadcasts:*"])],
    )
    created = await create_use_case(token, save_dto())
    assert created.created_by is None


async def _retried(repository: BroadcastRepository) -> BroadcastDto:
    retried = await _make(repository, BroadcastStatus.SCHEDULED)
    await repository.update_fields(retried.id, started_at=datetime_now())
    return retried


async def test_update_of_retried_scheduled_is_refused(
    update_use_case: UpdateBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    retried = await _retried(broadcast_repository)
    with pytest.raises(ConflictError) as error:
        await update_use_case(admin, UpdateBroadcastDto(broadcast_id=retried.id, data=save_dto()))
    assert error.value.code is ErrorCode.BROADCAST_INVALID_STATUS


async def test_media_of_retried_scheduled_is_refused(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    retried = await _retried(broadcast_repository)
    with pytest.raises(ConflictError) as error:
        await media_use_case(admin, _photo(retried.id))
    assert error.value.code is ErrorCode.BROADCAST_INVALID_STATUS


async def test_cancel_scheduled_resets_pending_rows(
    session: AsyncSession,
    cancel_use_case: CancelBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    user_repository: UserRepository,
    admin: UserDto,
) -> None:
    scheduled = await _make(broadcast_repository, BroadcastStatus.SCHEDULED)
    await _recipients(
        session,
        broadcast_repository,
        user_repository,
        scheduled,
        [BroadcastRecipientStatus.PENDING, BroadcastRecipientStatus.SENT],
        9450,
    )
    await cancel_use_case(admin, scheduled.id)
    assert await _statuses(session, scheduled.id) == [
        BroadcastRecipientStatus.CANCELED,
        BroadcastRecipientStatus.SENT,
    ]
    assert (await broadcast_repository.get_by_id(scheduled.id)).sent_count == 1


async def test_retry_after_recall_request_refused(
    session: AsyncSession,
    retry_use_case: RetryBroadcastUseCase,
    start_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    user_repository: UserRepository,
    admin: UserDto,
) -> None:
    done = await _make(broadcast_repository, BroadcastStatus.COMPLETED)
    await broadcast_repository.update_fields(done.id, recall_requested_at=datetime_now())
    await _recipients(
        session,
        broadcast_repository,
        user_repository,
        done,
        [BroadcastRecipientStatus.FAILED],
        9460,
    )
    with pytest.raises(ConflictError) as caught:
        await retry_use_case(admin, done.id)
    assert caught.value.code == ErrorCode.BROADCAST_INVALID_STATUS
    assert start_dispatch.messages == []


async def test_second_recall_refused(
    recall_use_case: RecallBroadcastUseCase,
    recall_dispatch: RecordingDispatch,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    done = await _make(broadcast_repository, BroadcastStatus.COMPLETED)
    await broadcast_repository.update_fields(done.id, started_at=datetime_now())
    await recall_use_case(admin, done.id)
    with pytest.raises(ConflictError) as caught:
        await recall_use_case(admin, done.id)
    assert caught.value.code == ErrorCode.BROADCAST_RECALL_IN_PROGRESS
    assert len(recall_dispatch.messages) == 1


async def test_summary_requires_its_permission_and_reports_statuses(
    broadcast_repository: BroadcastRepository, uow: UnitOfWork, admin: UserDto
) -> None:
    await _make(broadcast_repository, BroadcastStatus.FAILED)
    summary = await GetBroadcastSummaryUseCase(broadcast_repository, uow)(admin)
    assert summary.by_status[BroadcastStatus.FAILED] == 1
    user = SyntheticActor(
        id=0, role=Role.USER, name="t", is_privileged=True, log="[t]", permission_grants=[]
    )
    with pytest.raises(PermissionDeniedError):
        await GetBroadcastSummaryUseCase(broadcast_repository, uow)(user)


async def test_create_rejects_too_long_title(
    create_use_case: CreateBroadcastUseCase, admin: UserDto
) -> None:
    with pytest.raises(ValidationError) as caught:
        await create_use_case(admin, save_dto(title="x" * 121))
    assert caught.value.code == ErrorCode.BROADCAST_TITLE_TOO_LONG


async def test_media_moves_the_uploaded_file_into_place(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    broadcast = await _make(broadcast_repository)
    data = _photo(broadcast.id)

    await media_use_case(admin, data)

    assert not data.source.exists()
    assert media_path(media_config.media_dir, broadcast.id, 1, "jpg").read_bytes() == b"\xff" * 100


async def test_rejected_media_leaves_the_upload_for_the_caller_to_remove(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    broadcast = await _make(broadcast_repository)
    data = _media(broadcast.id, "application/x-msdownload", b"x")

    with pytest.raises(ValidationError):
        await media_use_case(admin, data)

    assert data.source.exists()
    data.source.unlink()


async def test_test_send_rejects_email_only_broadcast(
    user_repository: UserRepository,
    broadcast_repository: BroadcastRepository,
    settings_repository: SettingsRepository,
    promocode_repository: PromocodeRepository,
    translation_repository: TranslationRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    with_token: None,
) -> None:
    actor = await user_repository.create(
        CreateUserDto(name="Zed", role=Role.ADMIN, login="bc-tester4", telegram_id=9460)
    )
    telegram = MockTelegram(ok_response)
    use_case = _test_use_case(
        telegram,
        broadcast_repository,
        settings_repository,
        promocode_repository,
        translation_repository,
        media_config,
        uow,
    )
    email_only = await _make(broadcast_repository, delivery=BroadcastDelivery.EMAIL, contents={})
    with pytest.raises(ValidationError) as caught:
        await use_case(actor, email_only.id)
    assert caught.value.code == ErrorCode.BROADCAST_DELIVERY_INVALID
    assert telegram.requests == []


async def test_media_rejected_on_email_only_broadcast(
    media_use_case: SetBroadcastMediaUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    email_only = await _make(broadcast_repository, delivery=BroadcastDelivery.EMAIL, contents={})
    with pytest.raises(ValidationError) as caught:
        await media_use_case(admin, _photo(email_only.id))
    assert caught.value.code == ErrorCode.BROADCAST_DELIVERY_INVALID


async def test_media_can_always_be_removed_from_email_only_broadcast(
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    admin: UserDto,
) -> None:
    email_only = await _make(broadcast_repository, delivery=BroadcastDelivery.EMAIL, contents={})
    await broadcast_repository.update_fields(
        email_only.id, media_type=BroadcastMediaType.PHOTO, media_extension="jpg"
    )
    cleared = await DeleteBroadcastMediaUseCase(
        broadcast_repository, media_config, uow, event_publisher
    )(admin, email_only.id)
    assert cleared.media_type is None
