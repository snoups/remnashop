from datetime import datetime, timedelta, timezone

from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository


async def _create(
    repository: ApiTokenRepository,
    uow: UnitOfWork,
    *,
    name: str = "ci-script",
    token_hash: str = "hash-1",
    permissions: list[Permission] = [Permission.BANNERS_UPLOAD],
) -> int:
    async with uow:
        token = await repository.create(
            CreateApiTokenDto(
                name=name,
                permissions=permissions,
                token_hash=token_hash,
                created_by_user_id=None,
                expires_at=None,
            )
        )
        await uow.commit()
    return token.id


async def test_create_then_get_active_by_hash(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork
) -> None:
    await _create(api_token_repository, uow, token_hash="abc123")

    found = await api_token_repository.get_active_by_hash("abc123")
    assert found is not None
    assert found.name == "ci-script"
    assert found.permissions == [Permission.BANNERS_UPLOAD]


async def test_get_active_by_hash_returns_none_for_unknown_hash(
    api_token_repository: ApiTokenRepository,
) -> None:
    found = await api_token_repository.get_active_by_hash("nope")
    assert found is None


async def test_revoked_token_not_returned_by_get_active_by_hash(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork
) -> None:
    token_id = await _create(api_token_repository, uow, token_hash="revoke-me")
    await api_token_repository.revoke_by_id(token_id)

    found = await api_token_repository.get_active_by_hash("revoke-me")
    assert found is None


async def test_list_not_revoked_excludes_revoked(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork
) -> None:
    kept_id = await _create(api_token_repository, uow, name="kept", token_hash="kept-hash")
    revoked_id = await _create(api_token_repository, uow, name="revoked", token_hash="revoked-hash")
    await api_token_repository.revoke_by_id(revoked_id)

    listed = await api_token_repository.list_not_revoked()
    listed_ids = {token.id for token in listed}
    assert kept_id in listed_ids
    assert revoked_id not in listed_ids


async def test_list_not_revoked_includes_expired(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork
) -> None:
    async with uow:
        expired = await api_token_repository.create(
            CreateApiTokenDto(
                name="expired",
                permissions=[Permission.BANNERS_UPLOAD],
                token_hash="expired-hash",
                created_by_user_id=None,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        await uow.commit()

    listed_ids = {token.id for token in await api_token_repository.list_not_revoked()}
    assert expired.id in listed_ids
    assert await api_token_repository.get_active_by_hash("expired-hash") is None


async def test_touch_last_used_sets_timestamp(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork
) -> None:
    token_id = await _create(api_token_repository, uow, token_hash="touch-me")

    before = await api_token_repository.get_active_by_hash("touch-me")
    assert before is not None
    assert before.last_used_at is None

    await api_token_repository.touch_last_used(token_id)

    after = await api_token_repository.get_active_by_hash("touch-me")
    assert after is not None
    assert after.last_used_at is not None


async def test_get_active_by_hash_excludes_expired_token(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await api_token_repository.create(
            CreateApiTokenDto(
                name="expired",
                permissions=[Permission.BANNERS_VIEW],
                token_hash="expired-hash",
                created_by_user_id=None,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        await uow.commit()

    found = await api_token_repository.get_active_by_hash("expired-hash")
    assert found is None


async def test_get_active_by_hash_allows_token_with_no_expiry(
    api_token_repository: ApiTokenRepository, uow: UnitOfWork
) -> None:
    async with uow:
        await api_token_repository.create(
            CreateApiTokenDto(
                name="forever",
                permissions=[Permission.BANNERS_VIEW],
                token_hash="forever-hash",
                created_by_user_id=None,
                expires_at=None,
            )
        )
        await uow.commit()

    found = await api_token_repository.get_active_by_hash("forever-hash")
    assert found is not None
