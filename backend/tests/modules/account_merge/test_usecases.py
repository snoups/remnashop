from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import OAuthIdentity, Referral, User
from app.core.db.uow import UnitOfWork
from app.core.enums import OAuthProvider, Role, SessionAudience
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.core.utils.time import datetime_now
from app.modules.account_merge.dto import GetMergePreviewDto, MergeAccountsDto
from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.account_merge.usecases import GetMergePreviewUseCase, MergeAccountsUseCase
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


@pytest.fixture
async def owner(user_repository: UserRepository) -> UserDto:
    return await user_repository.create(
        CreateUserDto(name="o", login="mergeowner", role=Role.OWNER)
    )


@pytest.fixture
def merge(
    session: AsyncSession,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> MergeAccountsUseCase:
    return MergeAccountsUseCase(
        user_repository, AccountMergeRepository(session), session_repository, uow, event_publisher
    )


@pytest.fixture
def preview(
    session: AsyncSession, user_repository: UserRepository, uow: UnitOfWork
) -> GetMergePreviewUseCase:
    return GetMergePreviewUseCase(user_repository, AccountMergeRepository(session), uow)


async def _fingerprint(preview, actor, target_id: int, source_id: int) -> str:
    result = await preview(actor, GetMergePreviewDto(target_id=target_id, source_id=source_id))
    return result.fingerprint


async def test_merge_moves_everything_and_anonymizes_source(
    merge, user_repository, owner, preview
) -> None:
    source = await user_repository.create(CreateUserDto(name="old", telegram_id=11))
    target = await user_repository.create(CreateUserDto(name="new", telegram_id=22))
    await user_repository.credit_points(source.id, Decimal(5))

    result = await merge(
        owner,
        MergeAccountsDto(
            target_id=target.id,
            source_id=source.id,
            choices={"telegram": "target", "name": "source"},
            fingerprint=await _fingerprint(preview, owner, target.id, source.id),
            client_ip="127.0.0.1",
        ),
    )

    assert (result.telegram_id, result.name, result.points) == (22, "old", Decimal(5))
    gone = await user_repository.find_by_id(source.id)
    assert gone is not None and gone.deleted_at is not None and gone.telegram_id is None


async def test_merge_requires_choice_for_every_conflict(
    merge, user_repository, owner, preview
) -> None:
    source = await user_repository.create(CreateUserDto(name="a", email="a@x.io"))
    target = await user_repository.create(CreateUserDto(name="a", email="b@x.io"))

    with pytest.raises(ValidationError) as error:
        await merge(
            owner,
            MergeAccountsDto(
                target_id=target.id,
                source_id=source.id,
                choices={},
                fingerprint=await _fingerprint(preview, owner, target.id, source.id),
                client_ip="127.0.0.1",
            ),
        )
    assert error.value.code == ErrorCode.MERGE_CHOICE_MISSING


async def test_merge_rejects_stale_preview(merge, preview, session, user_repository, owner) -> None:
    source = await user_repository.create(CreateUserDto(name="a", email="a@x.io"))
    target = await user_repository.create(CreateUserDto(name="a", email="b@x.io"))
    fingerprint = await _fingerprint(preview, owner, target.id, source.id)
    (await session.get_one(User, target.id)).email = "c@x.io"
    await session.flush()

    with pytest.raises(ValidationError) as error:
        await merge(
            owner,
            MergeAccountsDto(
                target_id=target.id,
                source_id=source.id,
                choices={"email": "source"},
                fingerprint=fingerprint,
                client_ip="127.0.0.1",
            ),
        )
    assert error.value.code == ErrorCode.MERGE_PREVIEW_STALE
    untouched = await user_repository.find_by_id(source.id)
    assert untouched is not None and untouched.deleted_at is None


async def test_merge_rejects_preview_when_source_became_staff(
    merge, preview, session, user_repository, owner
) -> None:
    source = await user_repository.create(CreateUserDto(name="a"))
    target = await user_repository.create(CreateUserDto(name="b"))
    fingerprint = await _fingerprint(preview, owner, target.id, source.id)
    (await session.get_one(User, source.id)).role = Role.ADMIN
    await session.flush()

    with pytest.raises(ValidationError) as error:
        await merge(
            owner,
            MergeAccountsDto(
                target_id=target.id,
                source_id=source.id,
                choices={},
                fingerprint=fingerprint,
                client_ip="127.0.0.1",
            ),
        )
    assert error.value.code == ErrorCode.MERGE_PREVIEW_STALE


async def test_merge_rejects_same_account(merge, user_repository, owner) -> None:
    user = await user_repository.create(CreateUserDto(name="u"))

    with pytest.raises(ValidationError) as error:
        await merge(
            owner,
            MergeAccountsDto(
                target_id=user.id,
                source_id=user.id,
                choices={},
                fingerprint="",
                client_ip="127.0.0.1",
            ),
        )
    assert error.value.code == ErrorCode.MERGE_SAME_ACCOUNT


async def test_merge_rejects_deleted_side(merge, user_repository, owner) -> None:
    source = await user_repository.create(CreateUserDto(name="s"))
    target = await user_repository.create(CreateUserDto(name="t"))
    await user_repository.anonymize(source.id)

    with pytest.raises(NotFoundError):
        await merge(
            owner,
            MergeAccountsDto(
                target_id=target.id,
                source_id=source.id,
                choices={},
                fingerprint="",
                client_ip="127.0.0.1",
            ),
        )


async def test_merge_rejects_two_staff_accounts(merge, user_repository, owner) -> None:
    admin = await user_repository.create(CreateUserDto(name="a", login="ma", role=Role.ADMIN))

    with pytest.raises(ValidationError) as error:
        await merge(
            owner,
            MergeAccountsDto(
                target_id=owner.id,
                source_id=admin.id,
                choices={},
                fingerprint="",
                client_ip="127.0.0.1",
            ),
        )
    assert error.value.code == ErrorCode.MERGE_BOTH_PRIVILEGED


async def test_staff_merge_needs_admins_manage(merge, user_repository) -> None:
    admin = await user_repository.create(CreateUserDto(name="a", login="mb", role=Role.ADMIN))
    customer = await user_repository.create(CreateUserDto(name="c", telegram_id=33))
    actor = UserDto(id=admin.id, name="a", role=Role.ADMIN, permission_grants=["USERS_MERGE"])

    # out of reach answers like a missing account, so staff ids can't be probed
    with pytest.raises(NotFoundError):
        await merge(
            actor,
            MergeAccountsDto(
                target_id=admin.id,
                source_id=customer.id,
                choices={},
                fingerprint="",
                client_ip="127.0.0.1",
            ),
        )


async def test_owner_source_hands_role_to_target(merge, user_repository, owner, preview) -> None:
    customer = await user_repository.create(CreateUserDto(name="c", telegram_id=44))

    result = await merge(
        owner,
        MergeAccountsDto(
            target_id=customer.id,
            source_id=owner.id,
            choices={"name": "source"},
            fingerprint=await _fingerprint(preview, owner, customer.id, owner.id),
            client_ip="127.0.0.1",
        ),
    )

    assert result.role == Role.OWNER
    assert result.login == "mergeowner" and result.telegram_id == 44


async def test_blocked_customer_does_not_block_owner(
    merge, user_repository, owner, preview
) -> None:
    customer = await user_repository.create(CreateUserDto(name="c", is_blocked=True))

    result = await merge(
        owner,
        MergeAccountsDto(
            target_id=owner.id,
            source_id=customer.id,
            choices={"name": "target"},
            fingerprint=await _fingerprint(preview, owner, owner.id, customer.id),
            client_ip="127.0.0.1",
        ),
    )

    assert result.is_blocked is False and result.role == Role.OWNER


async def test_merge_into_own_account_keeps_actor_sessions(
    merge, user_repository, session_repository, owner, preview
) -> None:
    customer = await user_repository.create(CreateUserDto(name="c", telegram_id=55))

    async def login(user_id: int) -> None:
        await session_repository.create(
            CreateSessionDto(
                user_id=user_id,
                refresh_token_hash=f"merge-{user_id}",
                ip_address="10.0.0.1",
                user_agent=None,
                expires_at=datetime_now() + timedelta(days=1),
                audience=SessionAudience.DASHBOARD,
            )
        )

    await login(owner.id)
    await login(customer.id)

    await merge(
        owner,
        MergeAccountsDto(
            target_id=owner.id,
            source_id=customer.id,
            choices={"name": "target"},
            fingerprint=await _fingerprint(preview, owner, owner.id, customer.id),
            client_ip="127.0.0.1",
        ),
    )

    assert len(await session_repository.list_active_by_user(owner.id)) == 1
    assert await session_repository.list_active_by_user(customer.id) == []


async def test_preview_counts_and_conflicts(preview, user_repository, owner) -> None:
    source = await user_repository.create(CreateUserDto(name="s", email="s@x.io"))
    target = await user_repository.create(CreateUserDto(name="t", email="t@x.io"))

    result = await preview(owner, GetMergePreviewDto(target_id=target.id, source_id=source.id))

    assert {c.key for c in result.conflicts} == {"email", "name"}
    assert result.source_counts.subscriptions == 0


async def test_preview_into_staff_does_not_count_dropped_credentials(
    preview, session: AsyncSession, user_repository, owner
) -> None:
    customer = await user_repository.create(CreateUserDto(name="c", telegram_id=55))
    session.add(OAuthIdentity(user_id=customer.id, provider=OAuthProvider.GITHUB, external_id="gh"))
    await session.flush()

    result = await preview(owner, GetMergePreviewDto(target_id=owner.id, source_id=customer.id))

    assert result.source_counts.oauth_identities == 0


async def test_preview_flags_a_referrer_that_would_loop_and_merge_drops_it(
    preview, merge, session: AsyncSession, user_repository, owner
) -> None:
    source, target, middle = [
        await user_repository.create(CreateUserDto(name=n)) for n in ("s", "t", "x")
    ]
    # target -> middle -> source: keeping source's referrer would loop through target
    session.add_all(
        [
            Referral(referrer_id=target.id, referred_id=middle.id, level=1),
            Referral(referrer_id=middle.id, referred_id=source.id, level=1),
        ]
    )
    await session.flush()

    result = await preview(owner, GetMergePreviewDto(target_id=target.id, source_id=source.id))

    assert [(c.side, c.referrer_id) for c in result.referrer_cycles] == [("source", middle.id)]
    await merge(
        owner,
        MergeAccountsDto(
            target_id=target.id,
            source_id=source.id,
            choices={"name": "target"},
            fingerprint=result.fingerprint,
            client_ip="127.0.0.1",
        ),
    )
    assert await session.scalar(select(Referral).where(Referral.referred_id == target.id)) is None


async def test_preview_reports_no_cycle_for_plain_or_mutual_referrers(
    preview, session: AsyncSession, user_repository, owner
) -> None:
    source, target, shared, other = [
        await user_repository.create(CreateUserDto(name=n)) for n in ("s", "t", "r", "o")
    ]
    session.add_all(
        [
            Referral(referrer_id=shared.id, referred_id=source.id, level=1),
            Referral(referrer_id=shared.id, referred_id=target.id, level=1),
            Referral(referrer_id=target.id, referred_id=other.id, level=1),
        ]
    )
    await session.flush()

    shared_result = await preview(
        owner, GetMergePreviewDto(target_id=target.id, source_id=source.id)
    )
    # target invited other: that link is mutual for this pair, not a loop
    mutual_result = await preview(
        owner, GetMergePreviewDto(target_id=other.id, source_id=target.id)
    )

    assert shared_result.referrer_cycles == []
    assert mutual_result.referrer_cycles == []
