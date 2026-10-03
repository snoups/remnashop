from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaymentGatewayType
from app.modules.gateways.repository import GatewayRepository


async def test_get_all_returns_every_gateway_type_with_defaults(
    gateway_repository: GatewayRepository,
) -> None:
    gateways = await gateway_repository.get_all()

    assert {g.type for g in gateways} == set(PaymentGatewayType)
    assert all(not g.is_active for g in gateways)


async def test_get_by_type_synthesizes_default_for_missing_row(
    gateway_repository: GatewayRepository,
) -> None:
    gateway = await gateway_repository.get_by_type(PaymentGatewayType.CRYPTOMUS)

    assert gateway.type == PaymentGatewayType.CRYPTOMUS
    assert not gateway.is_active
    assert not gateway.is_configured


async def test_update_settings_creates_row_and_marks_configured(
    gateway_repository: GatewayRepository,
) -> None:
    gateway = await gateway_repository.update_settings(
        PaymentGatewayType.CRYPTOMUS, {"merchant_id": "m1", "api_key": "secret"}
    )

    assert gateway.is_configured


async def test_update_settings_merges_without_dropping_existing_fields(
    gateway_repository: GatewayRepository,
) -> None:
    await gateway_repository.update_settings(PaymentGatewayType.CRYPTOMUS, {"merchant_id": "m1"})
    gateway = await gateway_repository.update_settings(
        PaymentGatewayType.CRYPTOMUS, {"api_key": "secret"}
    )

    # is_configured needs merchant_id and api_key, so the second call must
    # have kept the first one's merchant_id
    assert gateway.is_configured


async def test_settings_stored_encrypted_at_rest(
    gateway_repository: GatewayRepository, session: AsyncSession
) -> None:
    await gateway_repository.update_settings(
        PaymentGatewayType.CRYPTOMUS, {"merchant_id": "merchant-1", "api_key": "secret-value"}
    )

    # raw SQL: the ORM path would decrypt through EncryptedString
    row = (
        await session.execute(
            text("SELECT settings FROM payment_gateways WHERE type = :type"),
            {"type": PaymentGatewayType.CRYPTOMUS.value},
        )
    ).one()
    assert "secret-value" not in row.settings
    assert "merchant-1" not in row.settings


async def test_set_active_toggles_flag(gateway_repository: GatewayRepository) -> None:
    await gateway_repository.update_settings(PaymentGatewayType.WATA, {"api_key": "secret"})

    gateway = await gateway_repository.set_active(PaymentGatewayType.WATA, True)
    assert gateway.is_active

    gateway = await gateway_repository.set_active(PaymentGatewayType.WATA, False)
    assert not gateway.is_active


async def test_get_raw_settings_returns_stored_values(
    gateway_repository: GatewayRepository,
) -> None:
    await gateway_repository.update_settings(
        PaymentGatewayType.YOOKASSA, {"shop_id": "123", "api_key": "secret"}
    )

    values = await gateway_repository.get_raw_settings(PaymentGatewayType.YOOKASSA)
    assert values == {"shop_id": "123", "api_key": "secret"}


async def test_get_raw_settings_returns_empty_dict_for_unconfigured_gateway(
    gateway_repository: GatewayRepository,
) -> None:
    values = await gateway_repository.get_raw_settings(PaymentGatewayType.YOOKASSA)
    assert values == {}


async def test_reorder_persists_order_and_creates_missing_rows(
    gateway_repository: GatewayRepository,
) -> None:
    rest = [
        t
        for t in PaymentGatewayType
        if t not in (PaymentGatewayType.WATA, PaymentGatewayType.VALUTIX)
    ]
    ordered = [PaymentGatewayType.WATA, PaymentGatewayType.VALUTIX, *rest]

    gateways = await gateway_repository.reorder(ordered)
    assert [g.type for g in gateways] == ordered

    refreshed = await gateway_repository.get_all()
    assert refreshed[0].type == PaymentGatewayType.WATA
    assert refreshed[1].type == PaymentGatewayType.VALUTIX
