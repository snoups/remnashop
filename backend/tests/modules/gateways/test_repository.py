from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaymentGatewayType
from app.modules.gateways.repository import GatewaysRepository


async def test_get_all_returns_every_gateway_type_with_defaults(
    gateways_repository: GatewaysRepository,
) -> None:
    gateways = await gateways_repository.get_all()

    assert {g.type for g in gateways} == set(PaymentGatewayType)
    assert all(not g.is_active for g in gateways)


async def test_get_by_type_synthesizes_default_for_missing_row(
    gateways_repository: GatewaysRepository,
) -> None:
    gateway = await gateways_repository.get_by_type(PaymentGatewayType.CRYPTOMUS)

    assert gateway.type == PaymentGatewayType.CRYPTOMUS
    assert not gateway.is_active
    assert not gateway.is_configured


async def test_update_settings_creates_row_and_marks_configured(
    gateways_repository: GatewaysRepository,
) -> None:
    gateway = await gateways_repository.update_settings(
        PaymentGatewayType.CRYPTOMUS, {"merchant_id": "m1", "api_key": "secret"}
    )

    assert gateway.is_configured


async def test_update_settings_merges_without_dropping_existing_fields(
    gateways_repository: GatewaysRepository,
) -> None:
    await gateways_repository.update_settings(PaymentGatewayType.CRYPTOMUS, {"merchant_id": "m1"})
    gateway = await gateways_repository.update_settings(
        PaymentGatewayType.CRYPTOMUS, {"api_key": "secret"}
    )

    # is_configured requires both merchant_id and api_key -- true only if
    # the second call didn't wipe out merchant_id from the first.
    assert gateway.is_configured


async def test_settings_stored_encrypted_at_rest(
    gateways_repository: GatewaysRepository, session: AsyncSession
) -> None:
    await gateways_repository.update_settings(
        PaymentGatewayType.CRYPTOMUS, {"merchant_id": "merchant-1", "api_key": "secret-value"}
    )

    # Raw SQL, not session.get(PaymentGateway, ...) -- the ORM path runs the
    # EncryptedString type decorator and would transparently decrypt back to
    # plaintext, which is exactly the behavior this test needs to see past.
    row = (
        await session.execute(
            text("SELECT settings FROM payment_gateways WHERE type = :type"),
            {"type": PaymentGatewayType.CRYPTOMUS.value},
        )
    ).one()
    assert "secret-value" not in row.settings
    assert "merchant-1" not in row.settings


async def test_set_active_toggles_flag(gateways_repository: GatewaysRepository) -> None:
    await gateways_repository.update_settings(PaymentGatewayType.WATA, {"api_key": "secret"})

    gateway = await gateways_repository.set_active(PaymentGatewayType.WATA, True)
    assert gateway.is_active

    gateway = await gateways_repository.set_active(PaymentGatewayType.WATA, False)
    assert not gateway.is_active


async def test_get_raw_settings_returns_stored_values(
    gateways_repository: GatewaysRepository,
) -> None:
    await gateways_repository.update_settings(
        PaymentGatewayType.YOOKASSA, {"shop_id": "123", "api_key": "secret"}
    )

    values = await gateways_repository.get_raw_settings(PaymentGatewayType.YOOKASSA)
    assert values == {"shop_id": "123", "api_key": "secret"}


async def test_get_raw_settings_returns_empty_dict_for_unconfigured_gateway(
    gateways_repository: GatewaysRepository,
) -> None:
    values = await gateways_repository.get_raw_settings(PaymentGatewayType.YOOKASSA)
    assert values == {}


async def test_reorder_persists_order_and_creates_missing_rows(
    gateways_repository: GatewaysRepository,
) -> None:
    rest = [
        t
        for t in PaymentGatewayType
        if t not in (PaymentGatewayType.WATA, PaymentGatewayType.VALUTIX)
    ]
    ordered = [PaymentGatewayType.WATA, PaymentGatewayType.VALUTIX, *rest]

    gateways = await gateways_repository.reorder(ordered)
    assert [g.type for g in gateways] == ordered

    refreshed = await gateways_repository.get_all()
    assert refreshed[0].type == PaymentGatewayType.WATA
    assert refreshed[1].type == PaymentGatewayType.VALUTIX
