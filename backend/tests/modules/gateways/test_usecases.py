import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PaymentGatewayType, Role
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.modules.gateways.dto import ReorderGatewaysDto, UpdateGatewaySettingsDto
from app.modules.gateways.repository import GatewaysRepository
from app.modules.gateways.usecases import (
    ListGatewaysUseCase,
    ReorderGatewaysUseCase,
    ToggleGatewayActiveUseCase,
    UpdateGatewaySettingsUseCase,
)
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="admin", name="admin", role=Role.OWNER, language=Locale.EN)
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
    gateways_repository: GatewaysRepository, uow: UnitOfWork
) -> None:
    use_case = UpdateGatewaySettingsUseCase(gateways_repository, uow)
    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdateGatewaySettingsDto(type=PaymentGatewayType.CRYPTOMUS, values={"bogus": "x"}),
        )


async def test_update_gateway_settings_persists_values(
    gateways_repository: GatewaysRepository, uow: UnitOfWork
) -> None:
    use_case = UpdateGatewaySettingsUseCase(gateways_repository, uow)
    gateway = await use_case(
        OWNER,
        UpdateGatewaySettingsDto(
            type=PaymentGatewayType.CRYPTOMUS, values={"merchant_id": "m1", "api_key": "secret"}
        ),
    )
    assert gateway.is_configured


async def test_regular_user_cannot_update_gateway_settings(
    gateways_repository: GatewaysRepository, uow: UnitOfWork
) -> None:
    use_case = UpdateGatewaySettingsUseCase(gateways_repository, uow)
    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdateGatewaySettingsDto(
                type=PaymentGatewayType.CRYPTOMUS, values={"merchant_id": "m1"}
            ),
        )


async def test_toggle_rejects_activating_unconfigured_gateway(
    gateways_repository: GatewaysRepository, uow: UnitOfWork
) -> None:
    use_case = ToggleGatewayActiveUseCase(gateways_repository, uow)
    with pytest.raises(ValidationError):
        await use_case(OWNER, PaymentGatewayType.WATA)


async def test_toggle_activates_configured_gateway(
    gateways_repository: GatewaysRepository, uow: UnitOfWork
) -> None:
    settings_use_case = UpdateGatewaySettingsUseCase(gateways_repository, uow)
    await settings_use_case(
        OWNER,
        UpdateGatewaySettingsDto(type=PaymentGatewayType.WATA, values={"api_key": "secret"}),
    )

    toggle_use_case = ToggleGatewayActiveUseCase(gateways_repository, uow)
    gateway = await toggle_use_case(OWNER, PaymentGatewayType.WATA)
    assert gateway.is_active


async def test_reorder_rejects_incomplete_list(
    gateways_repository: GatewaysRepository, uow: UnitOfWork
) -> None:
    use_case = ReorderGatewaysUseCase(gateways_repository, uow)
    with pytest.raises(ValidationError):
        await use_case(OWNER, ReorderGatewaysDto(ordered_types=[PaymentGatewayType.WATA]))


async def test_reorder_accepts_full_permutation(
    gateways_repository: GatewaysRepository, uow: UnitOfWork
) -> None:
    use_case = ReorderGatewaysUseCase(gateways_repository, uow)
    reversed_types = list(reversed(list(PaymentGatewayType)))
    gateways = await use_case(OWNER, ReorderGatewaysDto(ordered_types=reversed_types))
    assert [g.type for g in gateways] == reversed_types
