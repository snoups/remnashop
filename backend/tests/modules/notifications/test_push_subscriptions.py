import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.notifications.dto import SubscribePushDto
from app.modules.notifications.render import NotificationRenderer
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.usecases import (
    DeletePushSubscriptionUseCase,
    ListPushSubscriptionsUseCase,
    SendTestPushUseCase,
    SubscribePushUseCase,
)
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.modules.notifications.conftest import NewSession

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc"


def _sub(session_id: int, endpoint: str = ENDPOINT) -> SubscribePushDto:
    return SubscribePushDto(
        endpoint=endpoint, p256dh="k", auth="a", user_agent="UA", session_id=session_id
    )


async def _admin(user_repository: UserRepository, uow: UnitOfWork, login: str) -> UserDto:
    async with uow:
        return await user_repository.create(
            CreateUserDto(login=login, name=login, role=Role.ADMIN, language=Locale.EN)
        )


async def test_same_browser_moves_to_the_admin_signed_in_now(
    user_repository: UserRepository,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    new_session: NewSession,
) -> None:
    first = await _admin(user_repository, uow, "first")
    second = await _admin(user_repository, uow, "second")
    subscribe = SubscribePushUseCase(notification_repository, uow)

    created = (await subscribe(first, _sub(await new_session(first.id)))).created
    created_again = (await subscribe(second, _sub(await new_session(second.id)))).created

    assert created and not created_again
    listing = ListPushSubscriptionsUseCase(notification_repository, uow)
    assert await listing(first, None) == []
    assert [s.endpoint for s in await listing(second, None)] == [ENDPOINT]


async def test_cannot_delete_someone_elses_subscription(
    user_repository: UserRepository,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    new_session: NewSession,
) -> None:
    owner_of_sub = await _admin(user_repository, uow, "first")
    other = await _admin(user_repository, uow, "second")
    sub = (
        await SubscribePushUseCase(notification_repository, uow)(
            owner_of_sub, _sub(await new_session(owner_of_sub.id))
        )
    ).subscription

    with pytest.raises(NotFoundError):
        await DeletePushSubscriptionUseCase(notification_repository, uow)(other, sub.id)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://wns2-par02p.notify.windows.com/w/?token=abc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://web.push.apple.com/abc",
    ],
)
async def test_browser_push_services_are_accepted(
    user_repository: UserRepository,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    new_session: NewSession,
    endpoint: str,
) -> None:
    admin = await _admin(user_repository, uow, "first")
    sub = (
        await SubscribePushUseCase(notification_repository, uow)(
            admin, _sub(await new_session(admin.id), endpoint=endpoint)
        )
    ).subscription
    assert sub.endpoint == endpoint


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1/push",
        "https://internal-svc/push",
        "https://fcm.googleapis.com.evil.example/push",
        "https://evilfcm.googleapis.com/push",
        "http://fcm.googleapis.com/fcm/send/abc",
    ],
)
async def test_other_push_endpoints_are_rejected(
    user_repository: UserRepository,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
    new_session: NewSession,
    endpoint: str,
) -> None:
    admin = await _admin(user_repository, uow, "first")

    with pytest.raises(ValidationError) as error:
        await SubscribePushUseCase(notification_repository, uow)(
            admin, _sub(await new_session(admin.id), endpoint=endpoint)
        )
    assert error.value.code is ErrorCode.PUSH_ENDPOINT_NOT_ALLOWED


async def test_test_push_text_is_rendered_inside_the_usecase(
    user_repository: UserRepository,
    notification_repository: NotificationRepository,
    uow: UnitOfWork,
) -> None:
    class _Factory:
        async def build(self) -> NotificationRenderer:
            return NotificationRenderer({}, Locale.EN)

    admin = await _admin(user_repository, uow, "first")
    use_case = SendTestPushUseCase(
        notification_repository,
        uow,
        object(),
        _Factory(),  # type: ignore[arg-type]
    )
    # input is no longer a ready message: the usecase builds it after its checks
    with pytest.raises(ValidationError):
        await use_case(admin)
