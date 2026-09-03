import pytest

from app.core.actor import SyntheticActor
from app.core.enums import Role
from app.core.exceptions import PermissionDeniedError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase


class _DummyUseCase(UseCase[None, None]):
    required_permission = Permission.USERS_DELETE

    async def _execute(self, actor, data: None) -> None:
        return None


async def test_permission_denied_actor_without_grant_raises_permission_denied() -> None:
    token_actor = SyntheticActor(
        id=0,
        role=Role.USER,
        name="API Token: ci",
        is_privileged=True,
        log="[api_token:ci]",
        permission_grants=[Permission.BANNERS_UPLOAD.value],
    )
    use_case = _DummyUseCase()

    with pytest.raises(PermissionDeniedError):
        await use_case(token_actor)
