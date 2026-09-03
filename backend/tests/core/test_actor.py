from app.core.actor import Actor, SyntheticActor
from app.core.enums import Role


def test_synthetic_actor_satisfies_actor_protocol() -> None:
    actor: Actor = SyntheticActor(
        id=0, role=Role.USER, name="API Token: ci", is_privileged=True, log="[api_token:ci]"
    )

    assert actor.id == 0
    assert actor.role == Role.USER
    assert actor.name == "API Token: ci"
    assert actor.is_privileged is True
    assert actor.log == "[api_token:ci]"
    assert actor.permission_grants is None
    assert actor.permission_revokes is None


def test_synthetic_actor_carries_permission_grants() -> None:
    actor = SyntheticActor(
        id=0,
        role=Role.USER,
        name="API Token: ci",
        is_privileged=True,
        log="[api_token:ci]",
        permission_grants=["BANNERS_UPLOAD"],
    )

    assert actor.permission_grants == ["BANNERS_UPLOAD"]
