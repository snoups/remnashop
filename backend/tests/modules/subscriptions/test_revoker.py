from sqlalchemy import update

from app.core.db.models.subscription import Subscription
from app.core.enums import SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.revoker import PanelSubscriptionRevoker
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore
from tests.modules.subscriptions.factories import make_plan_snapshot


async def test_revoke_all_by_user_deletes_the_users_live_panel_identities(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk,
    remnawave_store: FakeUserStore,
    uow,
) -> None:
    owner = await user_repository.create(CreateUserDto(name="gone", telegram_id=7301))
    bystander = await user_repository.create(CreateUserDto(name="stays", telegram_id=7302))
    live = await remnawave_sdk.users.create_user(_create_request("rs_live"))
    expired = await remnawave_sdk.users.create_user(_create_request("rs_expired"))
    already_deleted = await remnawave_sdk.users.create_user(_create_request("rs_deleted"))
    other = await remnawave_sdk.users.create_user(_create_request("rs_other"))
    async with uow:
        live_row = await _subscription(subscription_repository, owner.id, live.id)
        expired_row = await _subscription(subscription_repository, owner.id, expired.id)
        await subscription_repository.session.execute(
            update(Subscription)
            .where(Subscription.id == expired_row.id)
            .values(status=SubscriptionStatus.EXPIRED)
        )
        deleted_row = await _subscription(subscription_repository, owner.id, already_deleted.id)
        await subscription_repository.mark_deleted(deleted_row.id)
        await _subscription(subscription_repository, bystander.id, other.id)
    # the panel identity behind a DELETED row is already gone
    await remnawave_sdk.users.delete_user(already_deleted.id)

    await PanelSubscriptionRevoker(subscription_repository, remnawave_sdk).revoke_all_by_user(
        owner.id
    )

    assert live.id not in remnawave_store
    # an expired subscription still has a panel user, it goes too
    assert expired.id not in remnawave_store
    assert other.id in remnawave_store
    # rows are kept as history but can't be reconciled back to life
    for row in (live_row, expired_row):
        assert (await subscription_repository.get_by_id(row.id)).status == (
            SubscriptionStatus.DELETED
        )


def _create_request(username: str):
    from remnapy.models import CreateUserRequestDto  # noqa: PLC0415

    return CreateUserRequestDto(username=username, expire_at=datetime_now())


async def _subscription(
    subscription_repository: SubscriptionRepository, user_id: int, remnawave_user_id: int
):
    return await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user_id,
            remnawave_user_id=remnawave_user_id,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=0,
            device_limit=0,
            expire_at=datetime_now(),
            url="https://fake-panel.test/sub",
            plan_snapshot=make_plan_snapshot(),
        )
    )
