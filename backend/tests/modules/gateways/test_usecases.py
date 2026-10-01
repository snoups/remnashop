import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PaymentGatewayType, Role
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.modules.gateways.dto import (
    ReorderGatewaysDto,
    SetGatewayActiveDto,
    UpdateGatewaySettingsDto,
)
from app.modules.gateways.events import GatewayChangedEvent
from app.modules.gateways.repository import GatewaysRepository
from app.modules.gateways.usecases import (
    ListGatewaysUseCase,
    ReorderGatewaysUseCase,
    SetGatewayActiveUseCase,
    UpdateGatewaySettingsUseCase,
)
from app.modules.users.dto import UserDto

OWNER = UserDto(login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def test_owner_can_list_gateways(
    gateways_repository: GatewaysRepository,
    uow: UnitOfWork,
) -> None:
    use_case = ListGatewaysUseCase(gateways_repository, uow)
    gateways = await use_case(OWNER)
    assert len(gateways) == len(list(PaymentGatewayType))


async def test_regular_user_cannot_list_gateways(
    gateways_repository: GatewaysRepository,
    uow: UnitOfWork,
) -> None:
    use_case = ListGatewaysUseCase(gateways_repository, uow)
    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER)


async def test_update_gateway_settings_rejects_unknown_field(
    gateways_repository: GatewaysRepository, uow: UnitOfWork, event_publisher
) -> None:
    use_case = UpdateGatewaySettingsUseCase(gateways_repository, event_publisher, uow)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateGatewaySettingsDto(type=PaymentGatewayType.CRYPTOMUS, values={"bogus": "x"}),
        )


async def test_update_gateway_settings_persists_values(
    gateways_repository: GatewaysRepository, uow: UnitOfWork, event_publisher
) -> None:
    use_case = UpdateGatewaySettingsUseCase(gateways_repository, event_publisher, uow)
    gateway = await use_case(
        OWNER,
        UpdateGatewaySettingsDto(
            type=PaymentGatewayType.CRYPTOMUS, values={"merchant_id": "m1", "api_key": "secret"}
        ),
    )
    assert gateway.is_configured


async def test_regular_user_cannot_update_gateway_settings(
    gateways_repository: GatewaysRepository, uow: UnitOfWork, event_publisher
) -> None:
    use_case = UpdateGatewaySettingsUseCase(gateways_repository, event_publisher, uow)
    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdateGatewaySettingsDto(
                type=PaymentGatewayType.CRYPTOMUS, values={"merchant_id": "m1"}
            ),
        )


async def test_set_active_rejects_activating_unconfigured_gateway(
    gateways_repository: GatewaysRepository, uow: UnitOfWork, event_publisher
) -> None:
    use_case = SetGatewayActiveUseCase(gateways_repository, event_publisher, uow)
    with pytest.raises(ValidationError):
        await use_case(OWNER, SetGatewayActiveDto(type=PaymentGatewayType.WATA, is_active=True))


async def test_set_active_activates_configured_gateway(
    gateways_repository: GatewaysRepository, uow: UnitOfWork, event_publisher
) -> None:
    settings_use_case = UpdateGatewaySettingsUseCase(gateways_repository, event_publisher, uow)
    await settings_use_case(
        OWNER,
        UpdateGatewaySettingsDto(type=PaymentGatewayType.WATA, values={"api_key": "secret"}),
    )

    set_active_use_case = SetGatewayActiveUseCase(gateways_repository, event_publisher, uow)
    gateway = await set_active_use_case(
        OWNER, SetGatewayActiveDto(type=PaymentGatewayType.WATA, is_active=True)
    )
    assert gateway.is_active


async def test_set_active_disables_gateway_and_is_idempotent(
    gateways_repository: GatewaysRepository, uow: UnitOfWork, event_publisher
) -> None:
    use_case = SetGatewayActiveUseCase(gateways_repository, event_publisher, uow)
    disable = SetGatewayActiveDto(type=PaymentGatewayType.WATA, is_active=False)

    first = await use_case(OWNER, disable)
    second = await use_case(OWNER, disable)

    assert not first.is_active
    assert not second.is_active


async def test_reorder_rejects_incomplete_list(
    gateways_repository: GatewaysRepository, uow: UnitOfWork, event_publisher
) -> None:
    use_case = ReorderGatewaysUseCase(gateways_repository, event_publisher, uow)
    with pytest.raises(ValidationError):
        await use_case(OWNER, ReorderGatewaysDto(ordered_types=[PaymentGatewayType.WATA]))


async def test_reorder_accepts_full_permutation(
    gateways_repository: GatewaysRepository, uow: UnitOfWork, event_publisher
) -> None:
    use_case = ReorderGatewaysUseCase(gateways_repository, event_publisher, uow)
    reversed_types = list(reversed(list(PaymentGatewayType)))
    gateways = await use_case(OWNER, ReorderGatewaysDto(ordered_types=reversed_types))
    assert [g.type for g in gateways] == reversed_types


class _RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[object] = []

    async def publish(self, event: object) -> None:
        self.events.append(event)


async def test_settings_change_is_audited_by_field_name_only(
    gateways_repository: GatewaysRepository, uow: UnitOfWork
) -> None:
    publisher = _RecordingPublisher()
    use_case = UpdateGatewaySettingsUseCase(gateways_repository, publisher, uow)  # type: ignore[arg-type]

    await use_case(
        OWNER,
        UpdateGatewaySettingsDto(
            type=PaymentGatewayType.YOOKASSA, values={"shop_id": "42", "api_key": "secret-key"}
        ),
    )

    (event,) = publisher.events
    assert isinstance(event, GatewayChangedEvent)
    assert (event.action, event.gateway_type) == ("settings", "YOOKASSA")
    assert event.changed_fields == ["api_key", "shop_id"]
    assert "secret-key" not in repr(event)
