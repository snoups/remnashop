from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.ports import EventPublisher
from app.modules.connect_guide.catalog import ConnectCatalog
from app.modules.connect_guide.defaults import DEFAULT_CATALOG
from app.modules.connect_guide.dto import ResetConnectGuideDto, UpdateConnectGuideDto
from app.modules.connect_guide.repository import ConnectGuideRepository
from app.modules.connect_guide.usecases import (
    GetConnectGuideUseCase,
    GetPublicConnectGuideUseCase,
    ResetConnectGuideUseCase,
    UpdateConnectGuideUseCase,
)
from app.modules.users.dto import UserDto

OWNER = UserDto(name="owner", role=Role.OWNER)


def _catalog(button: dict[str, Any]) -> dict[str, Any]:
    return {
        "platforms": [
            {
                "id": "ios",
                "apps": [
                    {
                        "id": "happ",
                        "name": "Happ",
                        "steps": [{"title": {"en": "Add"}, "icon": "plus", "buttons": [button]}],
                    }
                ],
            }
        ]
    }


def test_default_catalog_covers_every_platform() -> None:
    assert len(DEFAULT_CATALOG.platforms) == 7
    # the default goes through the same validation as a dashboard write
    assert ConnectCatalog.model_validate(DEFAULT_CATALOG.model_dump(mode="json")) == DEFAULT_CATALOG


@pytest.mark.parametrize(
    "button",
    [
        {"kind": "external", "label": {"en": "Get"}, "url": "http://example.com"},
        {"kind": "external", "label": {"en": "Get"}, "url": "javascript:alert(1)"},
        {"kind": "deep_link", "label": {"en": "Add"}, "template": "happ://add/", "encode": "raw"},
        {
            "kind": "deep_link",
            "label": {"en": "Add"},
            "template": "javascript:{{SUBSCRIPTION_LINK}}",
            "encode": "raw",
        },
        {
            "kind": "deep_link",
            "label": {"en": "Add"},
            "template": "https://evil.example/?u={{SUBSCRIPTION_LINK}}",
            "encode": "component",
        },
        {
            "kind": "deep_link",
            "label": {"en": "Add"},
            "template": "intent://{{SUBSCRIPTION_LINK}}#Intent;end",
            "encode": "raw",
        },
        {"kind": "copy_link", "label": {}},
    ],
)
def test_catalog_refuses_unsafe_buttons(button: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ConnectCatalog.model_validate(_catalog(button))


def test_catalog_refuses_duplicates_and_two_recommended_apps() -> None:
    app = {
        "id": "happ",
        "name": "Happ",
        "featured": True,
        "steps": [{"title": {"en": "x"}, "icon": "plus"}],
    }
    with pytest.raises(ValidationError):
        ConnectCatalog.model_validate({"platforms": [{"id": "ios", "apps": [app, app]}]})
    with pytest.raises(ValidationError):
        ConnectCatalog.model_validate(
            {"platforms": [{"id": "ios", "apps": [app, {**app, "id": "other"}]}]}
        )
    with pytest.raises(ValidationError):
        ConnectCatalog.model_validate(
            {"platforms": [{"id": "ios", "apps": [app]}, {"id": "ios", "apps": [app]}]}
        )


async def test_round_trip_reset_and_public_view(
    session: AsyncSession, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    repository = ConnectGuideRepository(session)
    get = GetConnectGuideUseCase(repository, uow)
    public = GetPublicConnectGuideUseCase(repository, uow)

    default = await get(OWNER)
    assert (default.enabled, default.is_default, default.catalog) == (True, True, DEFAULT_CATALOG)

    catalog = ConnectCatalog.model_validate(
        _catalog({"kind": "copy_link", "label": {"en": "Copy"}})
    )
    saved = await UpdateConnectGuideUseCase(repository, event_publisher, uow)(
        OWNER, UpdateConnectGuideDto(enabled=False, catalog=catalog, client_ip="127.0.0.1")
    )
    assert (saved.enabled, saved.is_default, saved.catalog) == (False, False, catalog)
    assert (await get(OWNER)).catalog == catalog
    # switched off: the cabinet sees no catalog and keeps its plain link page
    assert (await public.execute()).platforms == []

    reset = await ResetConnectGuideUseCase(repository, event_publisher, uow)(
        OWNER, ResetConnectGuideDto(client_ip="127.0.0.1")
    )
    assert (reset.enabled, reset.is_default) == (True, True)
    assert await public.execute() == DEFAULT_CATALOG
