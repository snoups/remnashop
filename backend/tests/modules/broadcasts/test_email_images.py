from pathlib import Path

import pytest

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import BroadcastDelivery, BroadcastStatus, Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.modules.broadcasts.dto import (
    AddEmailImageDto,
    BroadcastDto,
    BroadcastEmailContentDto,
    EmailImageDto,
    GetEmailImageDto,
    UpdateBroadcastDto,
)
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.storage import email_image_path
from app.modules.broadcasts.usecases import (
    AddBroadcastEmailImageUseCase,
    DeleteBroadcastUseCase,
    GetBroadcastEmailImageUseCase,
    UpdateBroadcastUseCase,
)
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.broadcasts.test_repository import save_dto
from tests.modules.broadcasts.test_usecases import _make, _upload

_MB = 1024 * 1024


@pytest.fixture
async def admin(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="admin", role=Role.ADMIN, login="img-admin")
    )


@pytest.fixture
def media_config(config: AppConfig, tmp_path: Path) -> AppConfig:
    return config.model_copy(update={"media_dir": tmp_path})


@pytest.fixture
def add_use_case(
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> AddBroadcastEmailImageUseCase:
    return AddBroadcastEmailImageUseCase(broadcast_repository, media_config, uow, event_publisher)


@pytest.fixture
def get_use_case(
    broadcast_repository: BroadcastRepository, media_config: AppConfig, uow: UnitOfWork
) -> GetBroadcastEmailImageUseCase:
    return GetBroadcastEmailImageUseCase(broadcast_repository, media_config, uow)


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
def delete_use_case(
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> DeleteBroadcastUseCase:
    return DeleteBroadcastUseCase(broadcast_repository, media_config, uow, event_publisher)


def _image(
    broadcast_id: int, data: bytes = b"png", content_type: str = "image/png"
) -> AddEmailImageDto:
    return AddEmailImageDto(
        broadcast_id=broadcast_id,
        content_type=content_type,
        source=_upload(data),
        size=len(data),
    )


async def _email_broadcast(repository: BroadcastRepository, **overrides: object) -> BroadcastDto:
    return await _make(
        repository,
        delivery=BroadcastDelivery.EMAIL,
        contents={},
        email_contents={Locale.EN: BroadcastEmailContentDto(subject="Hi", html="<p>x</p>")},
        **overrides,
    )


def _html(*image_ids: int) -> str:
    return "".join(f'<p><img src="bc-image:{i}" alt=""></p>' for i in image_ids) or "<p>x</p>"


async def test_add_image_stores_file(
    add_use_case: AddBroadcastEmailImageUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    broadcast = await _email_broadcast(broadcast_repository)
    image = await add_use_case(admin, _image(broadcast.id))
    path = email_image_path(media_config.media_dir, broadcast.id, image.id, "png")
    assert path.read_bytes() == b"png"
    assert [i.id for i in await broadcast_repository.list_email_images(broadcast.id)] == [image.id]


@pytest.mark.parametrize(
    ("content_type", "size"),
    [("image/webp", 10), ("image/png", 0), ("image/png", _MB + 1)],
)
async def test_add_image_rejects(
    add_use_case: AddBroadcastEmailImageUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
    content_type: str,
    size: int,
) -> None:
    broadcast = await _email_broadcast(broadcast_repository)
    data = AddEmailImageDto(
        broadcast_id=broadcast.id, content_type=content_type, source=_upload(b""), size=size
    )
    with pytest.raises(ValidationError) as error:
        await add_use_case(admin, data)
    assert error.value.code is ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID


async def test_add_image_limit_of_ten(
    add_use_case: AddBroadcastEmailImageUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    broadcast = await _email_broadcast(broadcast_repository)
    for _ in range(10):
        await add_use_case(admin, _image(broadcast.id))
    with pytest.raises(ValidationError) as error:
        await add_use_case(admin, _image(broadcast.id))
    assert error.value.code is ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID


async def test_add_image_only_while_editable(
    add_use_case: AddBroadcastEmailImageUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    sending = await _email_broadcast(broadcast_repository, status=BroadcastStatus.SENDING)
    with pytest.raises(ConflictError) as error:
        await add_use_case(admin, _image(sending.id))
    assert error.value.code is ErrorCode.BROADCAST_INVALID_STATUS


async def test_add_image_requires_permission(
    add_use_case: AddBroadcastEmailImageUseCase, broadcast_repository: BroadcastRepository
) -> None:
    broadcast = await _email_broadcast(broadcast_repository)
    user = UserDto(id=77, name="u", role=Role.USER, language=Locale.EN)
    with pytest.raises(PermissionDeniedError):
        await add_use_case(user, _image(broadcast.id))


async def test_update_drops_unreferenced_images(
    add_use_case: AddBroadcastEmailImageUseCase,
    update_use_case: UpdateBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    broadcast = await _email_broadcast(broadcast_repository)
    first = await add_use_case(admin, _image(broadcast.id))
    second = await add_use_case(admin, _image(broadcast.id))
    await update_use_case(
        admin,
        UpdateBroadcastDto(
            broadcast_id=broadcast.id,
            data=save_dto(
                delivery=BroadcastDelivery.EMAIL,
                contents={},
                email_contents={
                    Locale.EN: BroadcastEmailContentDto(subject="Hi", html=_html(first.id))
                },
            ),
        ),
    )
    assert [i.id for i in await broadcast_repository.list_email_images(broadcast.id)] == [first.id]
    assert email_image_path(media_config.media_dir, broadcast.id, first.id, "png").exists()
    assert not email_image_path(media_config.media_dir, broadcast.id, second.id, "png").exists()


async def test_update_checks_letter_budget(
    add_use_case: AddBroadcastEmailImageUseCase,
    update_use_case: UpdateBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    broadcast = await _email_broadcast(broadcast_repository)
    ids = [
        (await add_use_case(admin, _image(broadcast.id, b"\x00" * (900 * 1024)))).id
        for _ in range(4)
    ]
    with pytest.raises(ValidationError) as error:
        await update_use_case(
            admin,
            UpdateBroadcastDto(
                broadcast_id=broadcast.id,
                data=save_dto(
                    delivery=BroadcastDelivery.EMAIL,
                    contents={},
                    email_contents={
                        Locale.EN: BroadcastEmailContentDto(subject="Hi", html=_html(*ids))
                    },
                ),
            ),
        )
    assert error.value.code is ErrorCode.BROADCAST_EMAIL_IMAGE_INVALID


async def test_delete_broadcast_removes_image_dir(
    add_use_case: AddBroadcastEmailImageUseCase,
    delete_use_case: DeleteBroadcastUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    broadcast = await _email_broadcast(broadcast_repository)
    image = await add_use_case(admin, _image(broadcast.id))
    path = email_image_path(media_config.media_dir, broadcast.id, image.id, "png")
    assert path.exists()
    await delete_use_case(admin, broadcast.id)
    assert not path.parent.exists()


async def test_get_image_returns_file(
    add_use_case: AddBroadcastEmailImageUseCase,
    get_use_case: GetBroadcastEmailImageUseCase,
    broadcast_repository: BroadcastRepository,
    media_config: AppConfig,
    admin: UserDto,
) -> None:
    broadcast = await _email_broadcast(broadcast_repository)
    image: EmailImageDto = await add_use_case(admin, _image(broadcast.id))
    file = await get_use_case(admin, GetEmailImageDto(broadcast_id=broadcast.id, image_id=image.id))
    assert file.content_type == "image/png"
    assert file.path == email_image_path(media_config.media_dir, broadcast.id, image.id, "png")


async def test_get_image_from_other_broadcast_404(
    add_use_case: AddBroadcastEmailImageUseCase,
    get_use_case: GetBroadcastEmailImageUseCase,
    broadcast_repository: BroadcastRepository,
    admin: UserDto,
) -> None:
    first = await _email_broadcast(broadcast_repository)
    other = await _email_broadcast(broadcast_repository)
    image = await add_use_case(admin, _image(first.id))
    with pytest.raises(NotFoundError) as error:
        await get_use_case(admin, GetEmailImageDto(broadcast_id=other.id, image_id=image.id))
    assert error.value.code is ErrorCode.BROADCAST_NOT_FOUND
