from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.api.dependencies.admin import require_admin
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.enums import BlacklistKind
from app.modules.blacklist.api.schemas import (
    AddSourceRequest,
    BlacklistResponse,
    BlacklistSourceListResponse,
    BlacklistSourceResponse,
    UpdateSourceRequest,
)
from app.modules.blacklist.dto import (
    AddBlacklistSourceDto,
    BlacklistEntryInputDto,
    UpdateBlacklistSourceDto,
)
from app.modules.blacklist.usecases import (
    AddBlacklistEntryUseCase,
    AddBlacklistSourceUseCase,
    GetBlacklistSourceUseCase,
    ListBlacklistSourcesUseCase,
    ListBlacklistUseCase,
    RemoveBlacklistEntryUseCase,
    RemoveBlacklistSourceUseCase,
    SyncBlacklistSourcesUseCase,
    UpdateBlacklistSourceUseCase,
)

router = APIRouter(prefix="/blacklist", tags=["blacklist"])


@router.get("", response_model=BlacklistResponse)
@inject
async def get_blacklist(
    use_case: FromDishka[ListBlacklistUseCase],
    actor: Actor = Depends(require_admin),
) -> BlacklistResponse:
    blacklist = await use_case(actor)
    return BlacklistResponse.model_validate(blacklist, from_attributes=True)


@router.put(
    "/entries/{kind}/{value}", response_model=BlacklistResponse, responses=error_responses(400)
)
@inject
async def add_blacklist_entry(
    kind: BlacklistKind,
    value: str,
    use_case: FromDishka[AddBlacklistEntryUseCase],
    actor: Actor = Depends(require_admin),
) -> BlacklistResponse:
    blacklist = await use_case(actor, BlacklistEntryInputDto(kind=kind, value=value))
    return BlacklistResponse.model_validate(blacklist, from_attributes=True)


@router.delete("/entries/{kind}/{value}", response_model=BlacklistResponse)
@inject
async def remove_blacklist_entry(
    kind: BlacklistKind,
    value: str,
    use_case: FromDishka[RemoveBlacklistEntryUseCase],
    actor: Actor = Depends(require_admin),
) -> BlacklistResponse:
    blacklist = await use_case(actor, BlacklistEntryInputDto(kind=kind, value=value))
    return BlacklistResponse.model_validate(blacklist, from_attributes=True)


@router.get("/sources", response_model=BlacklistSourceListResponse)
@inject
async def list_blacklist_sources(
    use_case: FromDishka[ListBlacklistSourcesUseCase],
    actor: Actor = Depends(require_admin),
) -> BlacklistSourceListResponse:
    sources = await use_case(actor)
    items = [
        BlacklistSourceResponse.model_validate(source, from_attributes=True) for source in sources
    ]
    return BlacklistSourceListResponse(items=items, total=len(items))


@router.get(
    "/sources/{source_id:int}",
    response_model=BlacklistSourceResponse,
    responses=error_responses(404),
)
@inject
async def get_blacklist_source(
    source_id: int,
    use_case: FromDishka[GetBlacklistSourceUseCase],
    actor: Actor = Depends(require_admin),
) -> BlacklistSourceResponse:
    source = await use_case(actor, source_id)
    return BlacklistSourceResponse.model_validate(source, from_attributes=True)


@router.post(
    "/sources",
    response_model=BlacklistSourceResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(400, 409),
)
@inject
async def add_blacklist_source(
    payload: AddSourceRequest,
    use_case: FromDishka[AddBlacklistSourceUseCase],
    actor: Actor = Depends(require_admin),
) -> BlacklistSourceResponse:
    source = await use_case(actor, AddBlacklistSourceDto(url=payload.url, name=payload.name))
    return BlacklistSourceResponse.model_validate(source, from_attributes=True)


@router.delete("/sources/{source_id:int}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def remove_blacklist_source(
    source_id: int,
    use_case: FromDishka[RemoveBlacklistSourceUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor, source_id)


@router.patch(
    "/sources/{source_id:int}",
    response_model=BlacklistSourceResponse,
    responses=error_responses(404),
)
@inject
async def update_blacklist_source(
    source_id: int,
    payload: UpdateSourceRequest,
    use_case: FromDishka[UpdateBlacklistSourceUseCase],
    actor: Actor = Depends(require_admin),
) -> BlacklistSourceResponse:
    source = await use_case(
        actor, UpdateBlacklistSourceDto(source_id=source_id, enabled=payload.enabled)
    )
    return BlacklistSourceResponse.model_validate(source, from_attributes=True)


@router.post("/sources/actions/sync", status_code=status.HTTP_202_ACCEPTED)
@inject
async def sync_blacklist_sources(
    use_case: FromDishka[SyncBlacklistSourcesUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(actor)
