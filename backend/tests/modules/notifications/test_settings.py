import pytest
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from py_vapid.utils import b64urlencode
from pydantic import ValidationError as PydanticValidationError

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.exceptions import PermissionDeniedError
from app.core.ports import EventPublisher
from app.modules.notifications.api.schemas import UpdateNotificationSettingsRequest
from app.modules.notifications.dto import UpdateNotificationSettingsDto
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.usecases import (
    GenerateVapidKeysUseCase,
    GetNotificationSettingsUseCase,
    UpdateNotificationSettingsUseCase,
)
from app.modules.notifications.vapid import generate_vapid_keypair
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.events import RecordingEventPublisher
from tests.modules.notifications.conftest import NewSession

ADMIN = UserDto(id=99, login="a", name="a", role=Role.ADMIN, language=Locale.EN)


def test_generated_private_key_loads_in_pywebpush_and_matches_public() -> None:
    public, private = generate_vapid_keypair()
    vapid = Vapid.from_string(private_key=private)
    raw_public = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    assert b64urlencode(raw_public) == public


@pytest.fixture
async def owner(user_repository: UserRepository, uow: UnitOfWork) -> UserDto:
    async with uow:
        return await user_repository.create(
            CreateUserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
        )


async def test_generate_keys_wipes_subscriptions_and_configures_push(
    owner: UserDto,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    new_session: NewSession,
) -> None:
    async with uow:
        await notification_repository.upsert_push_subscription(
            user_id=owner.id,
            session_id=await new_session(owner.id),
            endpoint="https://push.example/1",
            p256dh="k",
            auth="a",
            user_agent=None,
        )
    use_case = GenerateVapidKeysUseCase(notification_repository, uow, event_publisher)
    result = await use_case(owner)

    assert result.is_push_configured
    assert await notification_repository.list_push_subscriptions(owner.id) == []
    settings = await GetNotificationSettingsUseCase(notification_repository, uow)(owner)
    assert settings.vapid_public_key == result.vapid_public_key


async def test_update_sets_contact(
    owner: UserDto, notification_repository: NotificationRepository, uow: UnitOfWork
) -> None:
    result = await UpdateNotificationSettingsUseCase(
        notification_repository, uow, RecordingEventPublisher()
    )(owner, UpdateNotificationSettingsDto(vapid_contact="mailto:ops@example.com"))
    assert result.vapid_contact == "mailto:ops@example.com"


async def test_admin_cannot_generate_keys(
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    use_case = GenerateVapidKeysUseCase(notification_repository, uow, event_publisher)
    with pytest.raises(PermissionDeniedError):
        await use_case(ADMIN)


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("ops@example.com", "mailto:ops@example.com"),
        ("  mailto:ops@example.com ", "mailto:ops@example.com"),
        ("https://example.com/abuse", "https://example.com/abuse"),
        ("", ""),
    ],
)
def test_contact_accepts_a_plain_email(raw: str, stored: str) -> None:
    assert UpdateNotificationSettingsRequest(vapid_contact=raw).vapid_contact == stored


def test_contact_rejects_garbage() -> None:
    with pytest.raises(PydanticValidationError):
        UpdateNotificationSettingsRequest(vapid_contact="not a contact")
