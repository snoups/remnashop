from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.admin import require_admin
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.blacklist.api.schemas import (
    AddSourceRequest,
    BlacklistEntryRequest,
    BlacklistResponse,
    BlacklistSourceResponse,
    ToggleSourceRequest,
)
from app.modules.blacklist.dto import (
    AddBlacklistSourceDto,
    BlacklistDto,
    BlacklistEntryInputDto,
    BlacklistSourceDto,
    ToggleBlacklistSourceDto,
)
from app.modules.blacklist.usecases import (
    AddBlacklistEntryUseCase,
    AddBlacklistSourceUseCase,
    ListBlacklistSourcesUseCase,
    ListBlacklistUseCase,
    RemoveBlacklistEntryUseCase,
    RemoveBlacklistSourceUseCase,
    SyncBlacklistSourcesUseCase,
    ToggleBlacklistSourceUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/blacklist", tags=["blacklist"])


def _to_response(blacklist: BlacklistDto) -> BlacklistResponse:
    return BlacklistResponse(telegram_ids=blacklist.telegram_ids, emails=blacklist.emails)


def _to_source_response(source: BlacklistSourceDto) -> BlacklistSourceResponse:
    return BlacklistSourceResponse(
        id=source.id,
        url=source.url,
        name=source.name,
        enabled=source.enabled,
        entries_count=source.entries_count,
        last_synced_at=source.last_synced_at,
        last_error=source.last_error,
    )


@router.get("", response_model=BlacklistResponse)
@inject
async def get_blacklist(
    use_case: FromDishka[ListBlacklistUseCase],
    actor: UserDto = Depends(require_admin),
) -> BlacklistResponse:
    blacklist = await use_case(actor)
    return _to_response(blacklist)


@router.post("/entries", response_model=BlacklistResponse)
@inject
async def add_blacklist_entry(
    payload: BlacklistEntryRequest,
    use_case: FromDishka[AddBlacklistEntryUseCase],
    actor: UserDto = Depends(require_admin),
) -> BlacklistResponse:
    try:
        blacklist = await use_case(
            actor, BlacklistEntryInputDto(kind=payload.kind, value=payload.value)
        )
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _to_response(blacklist)


@router.delete("/entries", response_model=BlacklistResponse)
@inject
async def remove_blacklist_entry(
    payload: BlacklistEntryRequest,
    use_case: FromDishka[RemoveBlacklistEntryUseCase],
    actor: UserDto = Depends(require_admin),
) -> BlacklistResponse:
    blacklist = await use_case(
        actor, BlacklistEntryInputDto(kind=payload.kind, value=payload.value)
    )
    return _to_response(blacklist)


@router.get("/sources", response_model=list[BlacklistSourceResponse])
@inject
async def list_blacklist_sources(
    use_case: FromDishka[ListBlacklistSourcesUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[BlacklistSourceResponse]:
    sources = await use_case(actor)
    return [_to_source_response(source) for source in sources]


@router.post("/sources", response_model=BlacklistSourceResponse)
@inject
async def add_blacklist_source(
    payload: AddSourceRequest,
    use_case: FromDishka[AddBlacklistSourceUseCase],
    actor: UserDto = Depends(require_admin),
) -> BlacklistSourceResponse:
    try:
        source = await use_case(actor, AddBlacklistSourceDto(url=payload.url, name=payload.name))
    except ValidationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_source_response(source)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def remove_blacklist_source(
    source_id: int,
    use_case: FromDishka[RemoveBlacklistSourceUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    await use_case(actor, source_id)


@router.patch("/sources/{source_id}", response_model=BlacklistSourceResponse)
@inject
async def toggle_blacklist_source(
    source_id: int,
    payload: ToggleSourceRequest,
    use_case: FromDishka[ToggleBlacklistSourceUseCase],
    actor: UserDto = Depends(require_admin),
) -> BlacklistSourceResponse:
    try:
        source = await use_case(
            actor, ToggleBlacklistSourceDto(source_id=source_id, enabled=payload.enabled)
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _to_source_response(source)


@router.post("/sources/sync", status_code=status.HTTP_202_ACCEPTED)
@inject
async def sync_blacklist_sources(
    use_case: FromDishka[SyncBlacklistSourcesUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    await use_case(actor)
